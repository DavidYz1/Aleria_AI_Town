"""Exercise real candidate boundaries, ranking, budgets and transaction ownership."""
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
import importlib

import pytest
from sqlalchemy import select, text

from backend.app.database.connection import create_engine_and_session
from backend.app.database.cognition_repository import CognitionRepository
from backend.app.database.models import Memory, WorldState
from backend.app.llm.embedding_provider import DeterministicEmbeddingProvider, normalize
from scripts.seed_world import seed_database
from tests.backend.test_cognition_repository import source_session


def api():
    return importlib.import_module("backend.app.agents.memory_retrieval")


def test_postgres_semantic_statement_binds_query_vector_without_live_database():
    import json
    from types import SimpleNamespace
    from sqlalchemy.dialects.postgresql.psycopg import dialect
    query = DeterministicEmbeddingProvider().embed("蓝色羽毛")
    class CompileSession:
        def get_bind(self): return SimpleNamespace(dialect=dialect())
        def execute(self, statement, parameters):
            compiled = statement.compile(dialect=dialect())
            assert "<=>" in str(compiled) and "CAST(" in str(compiled)
            assert ":query_vector" not in str(compiled)
            assert "query_vector" in compiled.params
            assert compiled.construct_params(parameters)["query_vector"] == json.dumps(list(query.vector))
            return []
    assert CognitionRepository(CompileSession()).semantic_scores(request(), query, expected_hashes={"a": "1" * 64}) == {}


def test_postgres_semantic_statement_binds_each_expected_id_hash_pair():
    from types import SimpleNamespace
    from sqlalchemy.dialects.postgresql.psycopg import dialect
    expected = {"a": "1" * 64, "b": "2" * 64}
    class CompileSession:
        def get_bind(self): return SimpleNamespace(dialect=dialect())
        def execute(self, statement, parameters):
            assert parameters["expected_memory_inputs"] == [("a", "1" * 64), ("b", "2" * 64)]
            compiled = statement.params(**parameters).compile(dialect=dialect(), compile_kwargs={"render_postcompile": True})
            assert "(memories.id, memories.embedding_input_hash) IN" in str(compiled)
            assert compiled.params["expected_memory_inputs_1_1"] == "a"
            assert compiled.params["expected_memory_inputs_1_2"] == "1" * 64
            assert compiled.params["expected_memory_inputs_2_1"] == "b"
            assert compiled.params["expected_memory_inputs_2_2"] == "2" * 64
            return []
    assert CognitionRepository(CompileSession()).semantic_scores(request(), DeterministicEmbeddingProvider().embed("query"), expected_hashes=expected) == {}


def test_changed_input_between_candidate_read_and_semantics_remains_lexical(memory_session):
    from sqlalchemy import update, tuple_
    add_memory(memory_session, "a")
    add_memory(memory_session, "b")
    class ConcurrentChange(CognitionRepository):
        def semantic_scores(self, request, query, **kwargs):
            # Simulate a committed READ COMMITTED change at the second-query
            # boundary while preserving the already-read ORM evidence snapshot.
            self.session.execute(update(Memory).where(Memory.id == "a").values(
                safe_summary="红色石头", embedding_input_hash="3" * 64).execution_options(synchronize_session=False))
            expected = kwargs.get("expected_hashes", {})
            ids = self.session.scalars(select(Memory.id).where(
                tuple_(Memory.id, Memory.embedding_input_hash).in_(list(expected.items()))))
            return {id: 1.0 for id in ids}
    result = api().MemoryRetriever(ConcurrentChange(memory_session), DeterministicEmbeddingProvider()).retrieve(request())
    assert result.mode == "hybrid"
    assert result.memory_ids == ("b", "a")
    assert result.memories[0].semantic == 1.0
    assert result.memories[1].semantic == 0.0 and result.memories[1].score == pytest.approx(.9)
    assert result.memories[1].content == "蓝色羽毛"


@pytest.fixture
def memory_session(database_url, seed_dir):
    seed_database(database_url, seed_dir)
    engine, factory = create_engine_and_session(database_url)
    with factory() as session:
        add_test_world(session)
        yield session
    engine.dispose()


def add_test_world(session):
    session.add(WorldState(id="retrieval-test-world", name="Retrieval fixture", day=1, time="09:00", clock_tick=9, world_version=7, event_sequence=0))
    session.commit()


def add_memory(session, id, text="蓝色羽毛", **changes):
    embedding = DeterministicEmbeddingProvider().embed(text)
    values = dict(id=id, world_id="retrieval-test-world", owner_npc_id="grey", memory_type="knowledge",
        authored_source_id=id, authored_source_version="1", content=text, safe_summary=text,
        normalized_content_hash=sha256(normalize(text).encode()).hexdigest(), related_entity_ids_json=[],
        occurred_world_version=1, occurred_clock_tick=9, created_world_version=1, created_clock_tick=9,
        occurred_world_time="09:00", source_created_at=datetime.now(UTC), importance=0.5, confidence=1,
        emotional_valence=0, secrecy="public", disclosure_scope="public", lifecycle_state="active",
        embedding_status="ready", embedding=list(embedding.vector), embedding_provider=embedding.provider,
        embedding_model=embedding.model, embedding_version=embedding.version,
        embedding_dimensions=embedding.dimensions, embedding_input_hash=embedding.input_hash, access_count=0)
    values.update(changes)
    row = Memory(**values)
    session.add(row)
    session.commit()
    return row


def request(**changes):
    return replace(api().RetrievalRequest(world_id="retrieval-test-world", owner_npc_id="grey",
        current_world_version=7, current_clock_tick=9, query_text="蓝色羽毛",
        scope=api().RetrievalScope.PLAYER_DIALOGUE, allowed_memory_types=frozenset(api().MemoryType),
        limit=6, char_budget=1600), **changes)


def test_hard_filters_precede_semantics_and_scores_are_stable(memory_session):
    s = memory_session
    for id, changes in [("relevant", {}), ("low-confidence", {"confidence": 0}),
        ("disputed", {"lifecycle_state": "disputed"}), ("important", {"text": "stone", "importance": 1}),
        ("recent", {"text": "stone"}), ("irrelevant", {"text": "stone", "occurred_clock_tick": 0}),
        ("secret", {"secrecy": "secret"}), ("private-only", {"disclosure_scope": "internal_only"}),
        ("future", {"occurred_world_version": 8}), ("future-tick", {"occurred_clock_tick": 10}),
        ("future-created", {"created_world_version": 8}), ("superseded", {"lifecycle_state": "superseded"}),
        ("other-world", {"world_id": "aleria-town"}),
        ("other-owner", {"owner_npc_id": "ryan"})]:
        add_memory(s, id, **changes)
    seen = []
    def semantic(row, query):
        seen.append(row.id)
        return 1.0 if row.safe_summary == "蓝色羽毛" else 0.0
    result = api().MemoryRetriever(CognitionRepository(s), DeterministicEmbeddingProvider(), semantic_scorer=semantic).retrieve(request())
    assert set(seen) == {"relevant", "low-confidence", "disputed", "important", "recent", "irrelevant"}
    assert result.memory_ids == ("relevant", "low-confidence", "disputed", "important", "recent", "irrelevant")
    assert result.scoring_version == "hybrid-v1"
    assert result.mode == "hybrid"
    assert result.memories[0].score == pytest.approx(.925)
    assert result.memories[2].score == pytest.approx(.925 * .85)
    assert not s.in_transaction()
    assert s.get(Memory, "relevant").access_count == 1


@pytest.mark.parametrize("scope,expected", [("PLAYER_DIALOGUE", ("a", "b")), ("INTERNAL_REFLECTION", ("a", "b", "c")), ("PUBLIC_EXPLANATION", ("a",))])
def test_scope_matrix_and_read_only_public_explanation(memory_session, scope, expected):
    add_memory(memory_session, "a")
    add_memory(memory_session, "b", secrecy="private", disclosure_scope="player_dialogue")
    add_memory(memory_session, "c", secrecy="secret", disclosure_scope="internal_only")
    result = api().MemoryRetriever(CognitionRepository(memory_session), DeterministicEmbeddingProvider()).retrieve(request(scope=getattr(api().RetrievalScope, scope)))
    assert result.memory_ids == expected
    assert not memory_session.in_transaction()
    assert memory_session.get(Memory, "a").access_count == (0 if scope == "PUBLIC_EXPLANATION" else 1)


@pytest.mark.parametrize("failure", ["space", "query", "pgvector"])
def test_fallback_keeps_boundaries_and_id_ties(memory_session, failure):
    for id in ("b", "a", "secret"):
        add_memory(memory_session, id, secrecy="secret" if id == "secret" else "public", embedding_model="old" if failure == "space" else "sha256-features")
    class FailedProvider(DeterministicEmbeddingProvider):
        def embed(self, text): raise RuntimeError("private-key private-content")
    class FailedVectorRepository(CognitionRepository):
        def semantic_scores(self, request, query, *, expected_hashes):
            # An actual database error must be contained by the retrieval savepoint.
            return self.session.execute(text("SELECT missing_vector_function(1)"))
    seen = []
    def semantic(row, query):
        seen.append(row.id)
        return 1
    repo = FailedVectorRepository(memory_session) if failure == "pgvector" else CognitionRepository(memory_session)
    provider = FailedProvider() if failure == "query" else DeterministicEmbeddingProvider()
    result = api().MemoryRetriever(repo, provider, semantic_scorer=semantic).retrieve(request())
    assert result.mode == "lexical_fallback"
    assert result.memory_ids == ("a", "b")
    assert result.memories[0].score == pytest.approx(.9)
    assert seen == []
    assert not memory_session.in_transaction()


def test_whole_unicode_summaries_fit_budget_without_truncation(memory_session):
    add_memory(memory_session, "a", text="羽毛🪶")
    add_memory(memory_session, "b", text="羽毛🪶")
    result = api().MemoryRetriever(CognitionRepository(memory_session), DeterministicEmbeddingProvider()).retrieve(request(query_text="羽毛🪶", char_budget=5))
    assert result.memory_ids == ("a",)
    assert result.memories[0].content == "羽毛🪶"


def test_retrieval_rejects_caller_transaction_without_rolling_it_back(memory_session):
    add_memory(memory_session, "a")
    memory_session.get(Memory, "a").importance = .8
    transaction = memory_session.get_transaction()
    with pytest.raises(api().MemoryRetrievalError):
        api().MemoryRetriever(CognitionRepository(memory_session), DeterministicEmbeddingProvider()).retrieve(request())
    assert memory_session.get_transaction() is transaction
    assert memory_session.get(Memory, "a").importance == .8


def test_failed_access_telemetry_rolls_back_only_telemetry_and_keeps_result(memory_session):
    add_memory(memory_session, "a")
    class FailedTelemetry(CognitionRepository):
        def record_access(self, ids):
            super().record_access(ids)
            raise RuntimeError("private telemetry payload")
    result = api().MemoryRetriever(FailedTelemetry(memory_session), DeterministicEmbeddingProvider()).retrieve(request())
    assert result.memory_ids == ("a",)
    assert not memory_session.in_transaction()
    assert memory_session.get(Memory, "a").access_count == 0


def test_rollback_driver_error_is_reported_without_private_payload(memory_session, monkeypatch, caplog):
    add_memory(memory_session, "a")
    original_rollback = memory_session.rollback
    def reported_failure():
        original_rollback()
        raise RuntimeError("private claim API-key")
    monkeypatch.setattr(memory_session, "rollback", reported_failure)
    with pytest.raises(api().MemoryRetrievalError, match="^memory unavailable$"):
        api().MemoryRetriever(CognitionRepository(memory_session), DeterministicEmbeddingProvider()).retrieve(
            request(scope=api().RetrievalScope.PUBLIC_EXPLANATION))
    assert not memory_session.in_transaction()
    assert "private claim API-key" not in caplog.text


def test_missing_or_stale_embeddings_never_enter_semantic_scorer(memory_session):
    add_memory(memory_session, "a", embedding_input_hash="0" * 64)
    add_memory(memory_session, "b", embedding_status="unavailable")
    add_memory(memory_session, "c", embedding_dimensions=16, embedding=[1.0] * 16)
    def forbidden_semantic(row, query):
        pytest.fail("incompatible embedding entered semantic comparison")
    result = api().MemoryRetriever(CognitionRepository(memory_session), DeterministicEmbeddingProvider(), semantic_scorer=forbidden_semantic).retrieve(request())
    assert result.mode == "lexical_fallback"
    assert result.memory_ids == ("a", "b", "c")


def test_empty_allowed_type_set_never_scores_or_returns_memories(memory_session):
    add_memory(memory_session, "a")
    result = api().MemoryRetriever(CognitionRepository(memory_session), DeterministicEmbeddingProvider()).retrieve(request(allowed_memory_types=frozenset()))
    assert result.memory_ids == ()
    assert not memory_session.in_transaction()


def test_mixed_spaces_keep_unembedded_memories_as_lexical_candidates(memory_session):
    add_memory(memory_session, "ready")
    add_memory(memory_session, "old-space", embedding_model="old")
    add_memory(memory_session, "unavailable", embedding_status="unavailable", embedding=None)
    seen = []
    def semantic(row, query):
        seen.append(row.id)
        return 1.0
    result = api().MemoryRetriever(CognitionRepository(memory_session), DeterministicEmbeddingProvider(), semantic_scorer=semantic).retrieve(request())
    assert seen == ["ready"]
    assert result.memory_ids == ("ready", "old-space", "unavailable")
    assert result.mode == "hybrid"
    assert [item.score for item in result.memories] == pytest.approx([.925, .9, .9])


def test_public_explanation_does_not_compare_claim_embeddings(source_session):
    from tests.backend.test_cognition_projection import add_turn
    from backend.app.services.cognition_projection import CognitionProjectionService, EmbeddingEnrichmentService
    add_turn(source_session)
    repository = CognitionRepository(source_session)
    CognitionProjectionService(repository, enrichment=EmbeddingEnrichmentService(repository, DeterministicEmbeddingProvider())).catch_up_owner("aleria-town", "grey")
    row = source_session.scalar(select(Memory).where(Memory.memory_type == "conversation"))
    row.secrecy, row.disclosure_scope = "public", "public"
    safe_summary = row.safe_summary
    source_session.commit()
    seen = []
    def semantic(row, query):
        seen.append(row.id)
        return 1.0
    result = api().MemoryRetriever(repository, DeterministicEmbeddingProvider(), semantic_scorer=semantic).retrieve(
        request(world_id="aleria-town", current_world_version=1, current_clock_tick=1, query_text="castle",
            scope=api().RetrievalScope.PUBLIC_EXPLANATION, allowed_memory_types=frozenset({api().MemoryType.CONVERSATION})))
    assert seen == []
    assert result.memories[0].content == safe_summary
    assert result.mode == "lexical_fallback"
    assert result.memories[0].lexical == 0  # castle appears only in the private claim payload


def test_opt_in_postgres_vector_permissions_and_fallback(postgres_database_url, seed_dir):
    seed_database(postgres_database_url, seed_dir)
    engine, factory = create_engine_and_session(postgres_database_url)
    try:
        with factory() as session:
            add_test_world(session)
            add_memory(session, "allowed")
            add_memory(session, "secret", secrecy="secret")
            add_memory(session, "legacy", embedding_model="old")
            add_memory(session, "unavailable", embedding=None, embedding_status="unavailable")
            result = api().MemoryRetriever(CognitionRepository(session), DeterministicEmbeddingProvider()).retrieve(request())
            assert result.memory_ids == ("allowed", "legacy", "unavailable")
            assert result.mode == "hybrid"
            class FailedProvider(DeterministicEmbeddingProvider):
                def embed(self, text): raise RuntimeError("unavailable")
            fallback = api().MemoryRetriever(CognitionRepository(session), FailedProvider()).retrieve(request())
            assert fallback.memory_ids == ("allowed", "legacy", "unavailable")
            assert fallback.mode == "lexical_fallback"
    finally:
        engine.dispose()
