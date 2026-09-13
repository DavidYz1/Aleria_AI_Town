"""Opt-in acceptance: TEST_POSTGRES_URL must be a disposable test database.

This migrates and resets the demo world in that database; never use live data.
The fixture removes only the fresh schema it creates, never a database or volume.
"""

from datetime import UTC, datetime
from hashlib import sha256

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, inspect, select, text

from backend.app.agents.memory_retrieval import (
    MemoryRetriever,
    MemoryType,
    RetrievalRequest,
    RetrievalScope,
)
from backend.app.core.config import Settings
from backend.app.database.connection import create_engine_and_session
from backend.app.database.cognition_repository import CognitionRepository
from backend.app.database.models import (
    AgentRun,
    ActionProposalRecord,
    Event,
    Memory,
    WorldAction,
    WorldState,
)
from backend.app.llm.embedding_provider import (
    DeterministicEmbeddingProvider,
    EmbeddingProviderError,
    normalize,
)
from backend.app.main import create_app
from scripts.seed_world import seed_database
from scripts.upgrade_schema import upgrade_schema


COGNITION_TABLES = {
    "agent_cognition_states",
    "observations",
    "memories",
    "memory_evidence",
    "beliefs",
    "belief_evidence",
}
VECTOR_QUERY = "pgvector acceptance cobalt compass"


def add_ready_memory(session, memory_id: str, *, owner: str = "grey", secrecy: str = "public") -> None:
    provider = DeterministicEmbeddingProvider()
    embedding = provider.embed(VECTOR_QUERY)
    disclosure = "internal_only" if secrecy == "secret" else "public"
    session.add(Memory(
        id=memory_id,
        world_id="aleria-town",
        owner_npc_id=owner,
        memory_type="knowledge",
        authored_source_id=memory_id,
        authored_source_version="stage2-postgres-acceptance-v1",
        content=VECTOR_QUERY,
        safe_summary=VECTOR_QUERY,
        normalized_content_hash=sha256(normalize(VECTOR_QUERY).encode()).hexdigest(),
        related_entity_ids_json=[],
        occurred_world_version=1,
        occurred_clock_tick=1,
        created_world_version=1,
        created_clock_tick=1,
        occurred_world_time="09:00",
        source_created_at=datetime.now(UTC),
        importance=0.5,
        confidence=1,
        emotional_valence=0,
        secrecy=secrecy,
        disclosure_scope=disclosure,
        lifecycle_state="active",
        embedding_status="ready",
        embedding=list(embedding.vector),
        embedding_provider=embedding.provider,
        embedding_model=embedding.model,
        embedding_version=embedding.version,
        embedding_dimensions=embedding.dimensions,
        embedding_input_hash=embedding.input_hash,
        access_count=0,
    ))


@pytest.mark.anyio
async def test_postgresql_pgvector_persists_one_complete_runtime(postgres_database_url, seed_dir):
    url = postgres_database_url
    engine, factory = create_engine_and_session(url)
    try:
        assert engine.dialect.name == "postgresql"
        assert engine.dialect.driver == "psycopg"
        upgrade_schema(url)
        seed_database(url, seed_dir)
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT extversion FROM pg_extension WHERE extname='vector'")) == "0.8.6"
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0004"
            assert connection.scalar(text(
                "SELECT udt_name FROM information_schema.columns "
                "WHERE table_schema=current_schema() AND table_name='memories' AND column_name='embedding'"
            )) == "vector"
        assert COGNITION_TABLES.issubset(inspect(engine).get_table_names())
        app = create_app(
            url,
            settings=Settings(_env_file=None, database_url=url),
        )
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                reset = await client.post("/api/demo/reset")
                assert reset.status_code == 200, reset.text
                response = await client.post("/api/world/tick", json={"expected_world_version": 0})
                assert response.status_code == 200
                data = response.json()["data"]
                run_id = data["run"]["id"]
                assert data["run"]["status"] == "completed"
                assert len(data["actions"]) == 3
                detail = await client.get(f"/api/agent-runs/{run_id}")
                assert detail.status_code == 200
                graph = detail.json()["data"]
                assert [proposal["ordinal"] for proposal in graph["proposals"]] == [0, 1, 2]
                assert [event["event_sequence"] for event in graph["events"]] == [1, 2, 3]
                assert [trace["sequence"] for trace in graph["trace"]] == list(range(1, 15))
                assert graph["trace"][0]["stage"] == "run_started"
                assert graph["trace"][-1]["stage"] == "run_completed"
            with factory() as session:
                assert session.scalar(select(func.count()).select_from(AgentRun).where(AgentRun.world_id == "aleria-town")) == 1
                for model in (ActionProposalRecord, WorldAction, Event):
                    assert session.scalar(select(func.count()).select_from(model).where(model.run_id == run_id)) == 3
                world = session.get(WorldState, "aleria-town")
                assert (world.world_version, world.clock_tick, world.event_sequence) == (1, 1, 3)
                ready_count = session.scalar(select(func.count()).select_from(Memory).where(
                    Memory.world_id == "aleria-town",
                    Memory.embedding_status == "ready",
                    Memory.embedding.is_not(None),
                ))
                assert ready_count > 0

                add_ready_memory(session, "vector-allowed-a")
                add_ready_memory(session, "vector-allowed-b")
                add_ready_memory(session, "vector-secret", secrecy="secret")
                add_ready_memory(session, "vector-other-owner", owner="ryan")
                session.commit()

                request = RetrievalRequest(
                    world_id="aleria-town",
                    owner_npc_id="grey",
                    current_world_version=1,
                    current_clock_tick=1,
                    query_text=VECTOR_QUERY,
                    scope=RetrievalScope.PUBLIC_EXPLANATION,
                    allowed_memory_types=frozenset({MemoryType.KNOWLEDGE}),
                    limit=10,
                    char_budget=1600,
                )
                provider = DeterministicEmbeddingProvider()
                first = MemoryRetriever(CognitionRepository(session), provider).retrieve(request)
                second = MemoryRetriever(CognitionRepository(session), provider).retrieve(request)
                assert first.mode == second.mode == "hybrid"
                assert first.error_code is second.error_code is None
                assert first.memory_ids == second.memory_ids == (
                    "vector-allowed-a",
                    "vector-allowed-b",
                )
                assert [item.semantic for item in first.memories] == pytest.approx([1.0, 1.0])

                class FailedProvider(DeterministicEmbeddingProvider):
                    def embed(self, text, *, timeout_seconds=None):
                        raise EmbeddingProviderError("PRIVATE provider payload")

                fallback = MemoryRetriever(
                    CognitionRepository(session),
                    FailedProvider(),
                ).retrieve(request)
                assert fallback.mode == "lexical_fallback"
                assert fallback.error_code == "embedding_unavailable"
                assert fallback.memory_ids == first.memory_ids
                assert all(item.semantic == 0 for item in fallback.memories)
                assert session.get(Memory, "vector-allowed-a").access_count == 0
        finally:
            app.state.session_factory.kw["bind"].dispose()
    finally:
        engine.dispose()
