import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from backend.app.core.config import Settings
from backend.app.database.connection import create_engine_and_session
from backend.app.database.models import AgentCognitionState, AgentPlan, Memory, NpcState, Observation
from backend.app.main import create_app
from scripts.seed_world import seed_database


@pytest.mark.anyio
async def test_get_npc_detail_returns_complete_public_contract_after_tick(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    transport = ASGITransport(app=create_app(database_url))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        tick_response = await client.post(
            "/api/world/tick",
            json={"expected_world_version": 0, "runtime_mode": "deterministic"},
        )
        response = await client.get("/api/npcs/ryan")

    assert tick_response.status_code == 200
    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": {
            "profile": {
                "id": "ryan",
                "name": "Ryan",
                "role": "Knight",
                "personality": ["optimistic", "brave", "kind"],
            },
            "state": {
                "location_id": "park",
                "location_name": "中央公园",
                "current_action": "work",
                "status": {
                    "energy": 70,
                    "mood": 75,
                    "social": 67,
                },
            },
            "world_context": {
                "day": 1,
                "time": "09:00",
                "clock_tick": 1,
                "time_phase": "morning",
            },
            "recent_actions": [
                {
                    "id": 1,
                    "clock_tick": 1,
                    "world_time": "09:00",
                    "action_type": "work",
                    "target_kind": None,
                    "target_id": None,
                    "target_name": None,
                    "reason_code": "knight_training",
                    "reason_text": "当前处于骑士训练时间，因此执行训练。",
                }
            ],
        },
        "message": "ok",
    }


@pytest.mark.anyio
async def test_get_npc_detail_returns_empty_history_before_first_tick(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    transport = ASGITransport(app=create_app(database_url))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/npcs/shir")

    assert response.status_code == 200
    assert response.json()["data"]["state"]["current_action"] == "eat"
    assert response.json()["data"]["recent_actions"] == []


@pytest.mark.anyio
async def test_get_npc_detail_limits_history_to_three_newest_actions(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    transport = ASGITransport(app=create_app(database_url))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for expected_world_version in range(4):
            tick_response = await client.post(
                "/api/world/tick",
                json={"expected_world_version": expected_world_version},
            )
            assert tick_response.status_code == 200

        response = await client.get("/api/npcs/ryan")

    assert response.status_code == 200
    recent_actions = response.json()["data"]["recent_actions"]
    assert [action["clock_tick"] for action in recent_actions] == [4, 3, 2]
    assert len(recent_actions) == 3


@pytest.mark.anyio
async def test_get_npc_detail_returns_404_for_unknown_profile(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    transport = ASGITransport(app=create_app(database_url))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/npcs/missing-npc")

    assert response.status_code == 404
    assert response.json() == {
        "success": False,
        "data": None,
        "message": "NPC not found",
    }


@pytest.mark.anyio
async def test_get_npc_detail_returns_safe_503_when_database_is_uninitialized(
    database_url,
):
    transport = ASGITransport(
        app=create_app(database_url),
        raise_app_exceptions=False,
    )
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/npcs/ryan")

    assert response.status_code == 503
    assert response.json() == {
        "success": False,
        "data": None,
        "message": "NPC detail is unavailable",
    }


@pytest.mark.anyio
async def test_get_npc_detail_returns_503_for_profile_without_state(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        state = session.get(NpcState, "ryan")
        assert state is not None
        session.delete(state)
        session.commit()

    transport = ASGITransport(app=create_app(database_url))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/npcs/ryan")

    assert response.status_code == 503
    assert response.json() == {
        "success": False,
        "data": None,
        "message": "NPC detail is unavailable",
    }


@pytest.mark.anyio
async def test_get_npc_memory_explanations_returns_the_public_envelope_after_tick(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    transport = ASGITransport(app=create_app(database_url))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        tick_response = await client.post(
            "/api/world/tick",
            json={"expected_world_version": 0},
        )
        world_before = await client.get("/api/world")
        response = await client.get("/api/npcs/ryan/memory-explanations")
        world_after = await client.get("/api/world")

    assert tick_response.status_code == 200
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "ok"
    data = body["data"]
    assert set(data) == {"npc_id", "retrieval_mode", "fallback_used", "memories"}
    assert data["npc_id"] == "ryan"
    assert data["retrieval_mode"] in {"hybrid", "lexical_fallback"}
    assert data["fallback_used"] is (data["retrieval_mode"] == "lexical_fallback")
    assert 0 < len(data["memories"]) <= 5
    kinds = set()
    for memory in data["memories"]:
        assert set(memory) == {
            "id",
            "type",
            "source",
            "summary",
            "occurred_clock_tick",
            "reason_text",
        }
        assert memory["type"] in {"episodic", "conversation", "reflection", "knowledge"}
        assert set(memory["source"]) == {"kind", "label"}
        assert memory["source"]["label"] in {
            "亲历事件",
            "听到的说法",
            "稳定知识",
            "形成的看法",
        }
        assert memory["occurred_clock_tick"] >= 0
        assert 0 < len(memory["summary"]) <= 240
        assert 0 < len(memory["reason_text"]) <= 120
        kinds.add(memory["source"]["kind"])
    assert "world_event" in kinds
    assert world_before.json()["data"]["world"]["world_version"] == 1
    assert world_after.json()["data"]["world"] == (
        world_before.json()["data"]["world"]
    )


@pytest.mark.anyio
async def test_get_npc_memory_explanations_never_exposes_the_player_claim(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    app = create_app(database_url, settings=Settings(_env_file=None))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # A tick gives Grey public episodic memories, so the private claim has to
        # be filtered out of a populated list rather than an empty one.
        tick_response = await client.post(
            "/api/world/tick",
            json={"expected_world_version": 0},
        )
        chat_response = await client.post(
            "/api/npcs/grey/chat",
            json={"message": "只有你知道：我把蓝色羽毛藏在低语森林的石堆下"},
        )
        response = await client.get("/api/npcs/grey/memory-explanations")

    assert tick_response.status_code == 200
    assert chat_response.status_code == 200
    assert response.status_code == 200
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        owned = session.scalars(
            select(Memory).where(Memory.owner_npc_id == "grey")
        ).all()
    claims = [row for row in owned if row.memory_type == "conversation"]
    assert len(claims) == 1
    assert "蓝色羽毛" in claims[0].content
    assert (claims[0].secrecy, claims[0].disclosure_scope) == (
        "private",
        "player_dialogue",
    )
    memories = response.json()["data"]["memories"]
    # The hard filter has to drop the claim from a list that is otherwise
    # populated, while still showing what Grey may disclose. An empty list would
    # make every assertion below vacuous.
    assert 0 < len(memories) < len(owned)
    assert "蓝色羽毛" not in response.text
    assert "石堆" not in response.text
    assert all(memory["type"] != "conversation" for memory in memories)


@pytest.mark.anyio
async def test_get_npc_memory_explanations_returns_404_for_unknown_profile(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    transport = ASGITransport(app=create_app(database_url))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/npcs/missing-npc/memory-explanations")

    assert response.status_code == 404
    assert response.json() == {
        "success": False,
        "data": None,
        "message": "NPC not found",
    }


@pytest.mark.anyio
async def test_get_npc_memory_explanations_returns_safe_503_when_cognition_is_unreadable(
    database_url,
):
    transport = ASGITransport(
        app=create_app(database_url),
        raise_app_exceptions=False,
    )
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/npcs/ryan/memory-explanations")

    assert response.status_code == 503
    assert response.json() == {
        "success": False,
        "data": None,
        "message": "NPC memory explanations are unavailable",
    }


@pytest.mark.anyio
async def test_public_explanation_route_runs_core_only_and_never_live_providers(
    database_url, seed_dir
):
    from backend.app.database.world_clock_repository import WorldTickRepository
    from backend.app.llm.embedding_provider import DeterministicEmbeddingProvider
    from backend.app.llm.reflection_provider import FakeReflectionProvider
    from backend.app.world.tick_engine import run_tick

    seed_database(database_url, seed_dir)
    seed_engine, factory = create_engine_and_session(database_url)
    with factory() as session:
        repository = WorldTickRepository(session)
        snapshot = repository.get_snapshot()
        repository.persist_tick(snapshot.world_version, run_tick(snapshot))
    seed_engine.dispose()

    class EmbeddingSpy(DeterministicEmbeddingProvider):
        def __init__(self):
            super().__init__()
            self.calls = 0

        def embed(self, text, *, timeout_seconds=None):
            self.calls += 1
            return super().embed(text)

    class ReflectionSpy(FakeReflectionProvider):
        def __init__(self):
            self.calls = 0

        def reflect(self, request):
            self.calls += 1
            return super().reflect(request)

    def cognition_state():
        engine, state_factory = create_engine_and_session(database_url)
        try:
            with state_factory() as session:
                state = session.get(AgentCognitionState, ("aleria-town", "ryan"))
                return (
                    session.scalar(select(func.count(Observation.id))),
                    session.scalar(select(func.count(Memory.id))),
                    None if state is None else (
                        state.last_event_sequence,
                        state.last_conversation_message_id,
                        state.reflection_memory_count,
                        state.reflection_accumulated_importance,
                        state.reflection_attempt_count,
                    ),
                    tuple(session.execute(select(
                        Memory.id, Memory.embedding_status
                    ).order_by(Memory.id)).all()),
                )
        finally:
            engine.dispose()

    embedding, reflection = EmbeddingSpy(), ReflectionSpy()
    settings = Settings(
        _env_file=None,
        reflection_importance_threshold=0,
        reflection_min_new_memories=1,
    )
    app = create_app(
        database_url,
        settings=settings,
        embedding_provider=embedding,
        reflection_provider=reflection,
    )
    before = cognition_state()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            first = await client.get("/api/npcs/ryan/memory-explanations")
            after_first = cognition_state()
            second = await client.get("/api/npcs/ryan/memory-explanations")
            after_second = cognition_state()
    finally:
        app.state.session_factory.kw["bind"].dispose()

    assert first.status_code == second.status_code == 200
    assert after_first[0] > before[0]
    assert after_first[1] > before[1]
    assert after_first[2][0] > 0
    assert after_second == after_first
    assert embedding.calls == 0
    assert reflection.calls == 0


@pytest.mark.anyio
async def test_npc_plan_cites_only_memories_the_player_may_see(database_url, seed_dir):
    """Planner 用 `INTERNAL_REFLECTION` 检索，那包含 secret 与 internal_only。

    计划落盘的 id 是**完整的**（内部可追溯），但 Plan API 只能返回其中独立通过
    公开硬过滤的那部分。私密记忆既不出现内容，也不以计数或占位符暴露 ——
    这与 `memory-explanations` 的既有规则一致：看不到的东西就是不出现。
    """
    seed_database(database_url, seed_dir)
    app = create_app(database_url, settings=Settings(_env_file=None))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        tick = await client.post("/api/world/tick", json={"expected_world_version": 0})
        chat = await client.post(
            "/api/npcs/grey/chat",
            json={"message": "只有你知道：我把蓝色羽毛藏在低语森林的石堆下"},
        )
        # 第一份计划建于 tick 0，那时只有预投影的 authored knowledge。公开的
        # episodic 记忆由 tick 自己产生，所以要推到下一份计划出现，它引用的
        # 才会同时包含公开与私密两类 —— 否则过滤断言跑在纯私密集合上。
        for version in range(1, 7):
            await client.post("/api/world/tick", json={"expected_world_version": version})
        response = await client.get("/api/npcs/grey/plan")

    assert (tick.status_code, chat.status_code, response.status_code) == (200, 200, 200)

    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        plan = session.scalars(
            select(AgentPlan).where(AgentPlan.owner_npc_id == "grey")
            .order_by(AgentPlan.created_clock_tick.desc())
        ).first()
        owned = session.scalars(select(Memory).where(Memory.owner_npc_id == "grey")).all()
    private = [m for m in owned if (m.secrecy, m.disclosure_scope) != ("public", "public")]

    # 非空前提三条：计划确实落盘了引用、被引用的里确实有私密的、公开的也确实有。
    assert plan is not None and plan.evidence_memory_ids_json, "计划必须记录引用的记忆"
    assert private, "本用例要求 grey 名下确实存在不可公开的记忆"
    cited_private = [m for m in private if m.id in plan.evidence_memory_ids_json]
    assert cited_private, "被引用的记忆里必须确实包含私密的，否则过滤断言是平凡的"

    shown = response.json()["data"]["current"]["evidence"]
    shown_ids = {item["id"] for item in shown}
    assert shown_ids, "公开的那部分必须仍然展示，空列表会让下面的断言全部平凡通过"
    assert shown_ids.isdisjoint({m.id for m in cited_private})
    assert len(shown_ids) < len(plan.evidence_memory_ids_json)
    assert "蓝色羽毛" not in response.text and "石堆" not in response.text
