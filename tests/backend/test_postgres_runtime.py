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
    AgentPlan,
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
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0006"
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
                # 本测试不传 runtime_mode，走默认 auto：`run_started` 之后每个 NPC
                # 各产生一条 planning trace（spec 3m §11），总数因此是 17 而不是 14。
                # docs/06 记的 1–14 描述的是**纯确定性**推进，两者都对。
                # 对照 tests/backend/test_agent_run_api.py 的同源断言。
                assert [trace["sequence"] for trace in graph["trace"]] == list(range(1, 18))
                assert [trace["stage"] for trace in graph["trace"][:4]] == [
                    "run_started", "planning", "planning", "planning",
                ]
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


@pytest.mark.anyio
async def test_demo_reset_clears_non_empty_procedural_memory_on_postgresql(
    postgres_database_url, seed_dir
):
    """Reset 必须在 PostgreSQL 上真的删掉**非空**的 `agent_plans`。

    上面的 acceptance 用例在第一个 tick **之前**就 reset，那时一条计划都还没有，
    因此它只证明了「删 0 行不报错」。Reset 清理 procedural memory 的逻辑
    （`backend/app/services/demo_reset_service.py`）此前只在 SQLite 上以非空
    数据验证过：同一批 delete 在 PostgreSQL 上由不同方言编译，并且与携带
    pgvector 列的 `memories` 处在同一个事务里。

    `agent_plans.source_run_id` 指向 `agent_runs`，删除顺序错了两个方言都会抛
    外键违约（SQLite 侧 `connection.py` 开了 `PRAGMA foreign_keys=ON`），
    所以这里验的不是「PG 才强制外键」，而是这条路径在 PG 上根本没跑过。
    留下活跃计划还会让 reset 后的第一个 tick 沿用上一个世界的计划而不重新规划。
    """
    url = postgres_database_url
    engine, factory = create_engine_and_session(url)

    def count(session, model):
        return session.scalar(
            select(func.count()).select_from(model).where(model.world_id == "aleria-town")
        )

    try:
        upgrade_schema(url)
        seed_database(url, seed_dir)
        app = create_app(url, settings=Settings(_env_file=None, database_url=url))
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                tick = await client.post("/api/world/tick", json={"expected_world_version": 0})
                assert tick.status_code == 200, tick.text

                with factory() as session:
                    plans_before = count(session, AgentPlan)
                    runs_before = count(session, AgentRun)
                # 非空前提：缺了这两条，下面的 `== 0` 在空表上恒真，什么都没证明。
                assert plans_before > 0, "tick 之后必须存在计划，否则本用例证明不了清理行为"
                assert runs_before > 0

                reset = await client.post("/api/demo/reset")
                assert reset.status_code == 200, reset.text

            with factory() as session:
                assert count(session, AgentPlan) == 0
                assert count(session, AgentRun) == 0
                world = session.get(WorldState, "aleria-town")
                assert (world.world_version, world.clock_tick) == (0, 0)
        finally:
            app.state.session_factory.kw["bind"].dispose()
    finally:
        engine.dispose()
