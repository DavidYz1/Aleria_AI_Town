import importlib
import hashlib
import math

import httpx
import pytest

from backend.app.core.config import Settings


def module():
    return importlib.import_module("backend.app.llm.embedding_provider")


def test_fake_normalizes_text_and_produces_stable_finite_unit_vectors():
    provider = module().DeterministicEmbeddingProvider(dimensions=32)
    first = provider.embed("  ＢＬＵＥ 蓝色羽毛  ")
    assert first == provider.embed("blue 蓝色羽毛")
    assert first.vector != provider.embed("红色石头").vector
    assert first.dimensions == len(first.vector) == 32
    assert first.provider == "deterministic-fake"
    assert first.input_hash == hashlib.sha256("blue 蓝色羽毛".encode()).hexdigest()
    assert all(math.isfinite(x) for x in first.vector)
    assert sum(x*x for x in first.vector) == pytest.approx(1)


def test_fake_segments_adjacent_latin_words_and_chinese_features():
    provider = module().DeterministicEmbeddingProvider()
    assert provider.embed("BLUE蓝色羽毛").vector == provider.embed("blue 蓝色羽毛").vector


@pytest.mark.parametrize("auth_mode", ["bearer", "none"])
def test_live_adapter_sends_bounded_embeddings_payload_and_short_timeout(auth_mode):
    seen = []
    def handle(request):
        import json
        seen.append(request)
        body = json.loads(request.content)
        assert body == {"model": "embed-test", "input": "羽" * 8000, "dimensions": 32}
        assert request.url.path == "/v1/embeddings"
        assert request.extensions["timeout"]["read"] == 3.0
        assert request.headers.get("Authorization") == ("Bearer test-key" if auth_mode == "bearer" else None)
        return httpx.Response(200, json={"data": [{"embedding": [1.0] * 32}]})
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        provider = module().OpenAICompatibleEmbeddingProvider(base_url="https://example.test/v1/", api_key="test-key", model="embed-test", auth_mode=auth_mode, dimensions=32, timeout_seconds=3, client=client)
        result = provider.embed("羽" * 9000)
    assert len(seen) == 1
    assert result.model == "embed-test"
    assert len(result.vector) == 32


@pytest.mark.parametrize("body", [{}, {"data": []}, {"data": [{"embedding": [1]}]}, {"data": [{"embedding": ["bad"] * 32}]}, {"data": [{"embedding": [0] * 32}]}])
def test_live_invalid_responses_are_safe(body, caplog):
    with httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=body))) as client:
        provider = module().OpenAICompatibleEmbeddingProvider(base_url="https://example.test/v1", api_key="test-key", model="embed-test", auth_mode="bearer", dimensions=32, timeout_seconds=3, client=client)
        with pytest.raises(module().EmbeddingProviderError) as error:
            provider.embed("private original text")
    assert "private original text" not in str(error.value) + caplog.text
    assert "test-key" not in str(error.value) + caplog.text


def test_live_nan_and_transport_errors_are_safe():
    for handler in (lambda req: httpx.Response(200, content='{"data":[{"embedding":[' + ','.join(['NaN'] * 32) + ']}]}'), lambda req: (_ for _ in ()).throw(httpx.ReadTimeout("private test-key"))):
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            provider = module().OpenAICompatibleEmbeddingProvider(base_url="https://example.test/v1", api_key="test-key", model="embed-test", auth_mode="bearer", dimensions=32, timeout_seconds=3, client=client)
            with pytest.raises(module().EmbeddingProviderError, match="embedding unavailable"):
                provider.embed("private")


def test_factory_requires_explicit_complete_live_configuration(caplog):
    assert isinstance(module().build_embedding_provider(Settings(_env_file=None)), module().DeterministicEmbeddingProvider)
    incomplete = Settings(_env_file=None, embedding_provider="openai_compatible", embedding_api_key="private-key")
    assert isinstance(module().build_embedding_provider(incomplete), module().DeterministicEmbeddingProvider)
    assert "embedding_configuration" in caplog.text
    assert "private-key" not in caplog.text
    complete = Settings(_env_file=None, embedding_provider="openai_compatible", embedding_base_url="https://example.test/v1", embedding_model="embed", embedding_auth_mode="none")
    assert isinstance(module().build_embedding_provider(complete), module().OpenAICompatibleEmbeddingProvider)


def test_enrichment_commits_ready_metadata_skips_unchanged_and_rebuilds_space(memory_session):
    from tests.backend.test_memory_retrieval import add_memory
    from backend.app.database.cognition_repository import CognitionRepository
    from backend.app.database.models import Memory
    from backend.app.services import cognition_projection
    add_memory(memory_session, "pending", embedding=None, embedding_status="unavailable")
    class ObservedProvider(module().DeterministicEmbeddingProvider):
        calls = 0
        def embed(self, text):
            assert not memory_session.in_transaction()  # never hold locks over HTTP
            self.calls += 1
            return super().embed(text)
    provider = ObservedProvider()
    service = cognition_projection.EmbeddingEnrichmentService(CognitionRepository(memory_session), provider)
    assert service.enrich_pending("retrieval-test-world", "grey", 12) == 1
    assert not memory_session.in_transaction()
    row = memory_session.get(Memory, "pending")
    assert row.embedding_status == "ready" and len(row.embedding) == 32
    assert row.embedding_input_hash == hashlib.sha256("蓝色羽毛".encode()).hexdigest()
    memory_session.rollback()
    assert service.enrich_pending("retrieval-test-world", "grey", 12) == 0
    assert provider.calls == 1
    memory_session.get(Memory, "pending").safe_summary = "红色石头"
    memory_session.commit()
    assert service.enrich_pending("retrieval-test-world", "grey", 12) == 1
    assert provider.calls == 2
    changed = cognition_projection.EmbeddingEnrichmentService(CognitionRepository(memory_session), ObservedProvider(dimensions=16))
    assert changed.enrich_pending("retrieval-test-world", "grey", 12) == 1
    assert memory_session.get(Memory, "pending").embedding_dimensions == 16


def test_failed_enrichment_preserves_core_checkpoint_and_later_sources(source_session):
    from sqlalchemy import select
    from backend.app.database.cognition_repository import CognitionRepository
    from backend.app.database.models import AgentCognitionState, Memory
    from backend.app.services import cognition_projection
    from tests.backend.test_cognition_projection import add_turn
    class FailedProvider(module().DeterministicEmbeddingProvider):
        def embed(self, text): raise RuntimeError("private original key")
    repository = CognitionRepository(source_session)
    service = cognition_projection.CognitionProjectionService(repository,
        enrichment=cognition_projection.EmbeddingEnrichmentService(repository, FailedProvider()))
    result = service.catch_up_owner("aleria-town", "grey")
    assert result.created_memories == 1
    row = source_session.scalar(select(Memory).where(Memory.memory_type == "episodic"))
    assert row.embedding_status == "failed"
    assert source_session.get(AgentCognitionState, ("aleria-town", "grey")).last_event_sequence == 3
    source_session.rollback()
    ids = add_turn(source_session)
    assert service.catch_up_owner("aleria-town", "grey").created_memories == 1
    assert source_session.get(AgentCognitionState, ("aleria-town", "grey")).last_conversation_message_id == ids[1]


# Reuse real temporary-database fixture infrastructure, never the development DB.
from tests.backend.test_memory_retrieval import memory_session
from tests.backend.test_cognition_repository import source_session


def test_enrichment_stops_starting_new_embeddings_after_deadline(memory_session):
    from tests.backend.test_memory_retrieval import add_memory
    from backend.app.database.cognition_repository import CognitionRepository
    from backend.app.database.models import Memory
    from backend.app.services.cognition_projection import EmbeddingEnrichmentService
    add_memory(memory_session, "a", embedding_status="unavailable")
    add_memory(memory_session, "b", embedding_status="unavailable")
    clock = [0.0]
    class SlowProvider(module().DeterministicEmbeddingProvider):
        def embed(self, text):
            clock[0] = 10.0
            return super().embed(text)
    service = EmbeddingEnrichmentService(CognitionRepository(memory_session), SlowProvider())
    assert service.enrich_pending("retrieval-test-world", "grey", 12, deadline=5, monotonic=lambda: clock[0]) == 1
    assert not memory_session.in_transaction()
    assert memory_session.get(Memory, "a").embedding_status == "ready"
    assert memory_session.get(Memory, "b").embedding_status == "unavailable"


def test_failed_old_entries_do_not_starve_never_attempted_entries(memory_session):
    from tests.backend.test_memory_retrieval import add_memory
    from backend.app.database.cognition_repository import CognitionRepository
    from backend.app.database.models import Memory
    from backend.app.services.cognition_projection import EmbeddingEnrichmentService
    for id, content in [("a", "poison a"), ("b", "poison b"), ("c", "healthy c"), ("d", "healthy d")]:
        add_memory(memory_session, id, text=content, embedding_status="unavailable", embedding=None)
    class SelectiveProvider(module().DeterministicEmbeddingProvider):
        calls = 0
        def embed(self, text):
            self.calls += 1
            if text.startswith("poison"):
                raise module().EmbeddingProviderError("embedding unavailable")
            return super().embed(text)
    provider = SelectiveProvider()
    for _ in range(2):
        before = provider.calls
        EmbeddingEnrichmentService(CognitionRepository(memory_session), provider).enrich_pending("retrieval-test-world", "grey", 2)
        assert provider.calls - before <= 2
        assert not memory_session.in_transaction()
    assert memory_session.get(Memory, "c").embedding_status == "ready"
    assert memory_session.get(Memory, "d").embedding_status == "ready"
    assert memory_session.get(Memory, "a").embedding_status == "failed"


def test_failed_retry_rotation_reaches_later_recoverable_entries_across_services(memory_session):
    from tests.backend.test_memory_retrieval import add_memory
    from backend.app.database.cognition_repository import CognitionRepository
    from backend.app.database.models import Memory
    from backend.app.services.cognition_projection import EmbeddingEnrichmentService
    for id, content in [("a", "poison a"), ("b", "poison b"), ("c", "recoverable c")]:
        add_memory(memory_session, id, text=content, embedding_status="failed", embedding=None)
    class SelectiveProvider(module().DeterministicEmbeddingProvider):
        calls = 0
        def embed(self, text):
            self.calls += 1
            if text.startswith("poison"):
                raise module().EmbeddingProviderError("embedding unavailable")
            return super().embed(text)
    provider = SelectiveProvider()
    for _ in range(3):
        before = provider.calls
        EmbeddingEnrichmentService(CognitionRepository(memory_session), provider).enrich_pending("retrieval-test-world", "grey", 1)
        assert provider.calls - before == 1
        assert not memory_session.in_transaction()
    assert memory_session.get(Memory, "c").embedding_status == "ready"


@pytest.mark.parametrize("boundary", ["world", "owner", "space"])
def test_retry_progress_does_not_skip_first_entry_in_another_scope(memory_session, boundary):
    from tests.backend.test_memory_retrieval import add_memory
    from backend.app.database.cognition_repository import CognitionRepository
    from backend.app.database.models import Memory, WorldState
    from backend.app.services.cognition_projection import EmbeddingEnrichmentService
    add_memory(memory_session, "a", text="initial failure", embedding_status="failed")
    add_memory(memory_session, "z", text="later entry", embedding_status="failed")
    class FailedProvider(module().DeterministicEmbeddingProvider):
        def embed(self, text): raise module().EmbeddingProviderError("embedding unavailable")
    EmbeddingEnrichmentService(CognitionRepository(memory_session), FailedProvider()).enrich_pending("retrieval-test-world", "grey", 1)
    world, owner = "retrieval-test-world", "grey"
    if boundary == "space":
        target, dimensions = "a", 16
    else:
        target, dimensions = "0-target", 32
        if boundary == "world":
            world = "retry-other-world"
            memory_session.add(WorldState(id=world, name="Retry isolation", day=1, time="09:00", clock_tick=9, world_version=7, event_sequence=0))
            memory_session.commit()
        else:
            owner = "ryan"
        add_memory(memory_session, target, world_id=world, owner_npc_id=owner, embedding_status="failed")
        add_memory(memory_session, "z-target", world_id=world, owner_npc_id=owner, embedding_status="failed")
    EmbeddingEnrichmentService(CognitionRepository(memory_session), module().DeterministicEmbeddingProvider(dimensions=dimensions)).enrich_pending(world, owner, 1)
    assert memory_session.get(Memory, target).embedding_status == "ready"
    assert memory_session.get(Memory, target).embedding_dimensions == dimensions
