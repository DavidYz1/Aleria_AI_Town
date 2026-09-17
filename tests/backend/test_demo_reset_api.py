import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from backend.app.database.connection import create_engine_and_session
from backend.app.database.models import (
    AgentCognitionState,
    AgentPlan,
    Belief,
    BeliefEvidence,
    Conversation,
    ConversationMessage,
    Event,
    Memory,
    MemoryEvidence,
    NpcState,
    Observation,
    PlayerState,
    QuestEvent,
    QuestProgress,
    WorldAction,
    WorldState,
)
from datetime import UTC, datetime
from uuid import uuid4
from backend.app.llm.mock import MockChatProvider
from backend.app.main import create_app
from scripts.seed_world import seed_database


@pytest.mark.anyio
async def test_reset_demo_restores_canonical_state_and_removes_demo_history(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    app = create_app(database_url, chat_provider=MockChatProvider())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        accepted = await client.post(
            "/api/quests/missing-child/interact",
            json={
                "interaction": "accept_quest",
                "expected_version": 0,
                "expected_world_version": 0,
            },
        )
        ticked = await client.post(
            "/api/world/tick",
            json={"expected_world_version": 1},
        )
        chatted = await client.post(
            "/api/npcs/ryan/chat",
            json={"conversation_id": None, "message": "你好"},
        )
        travelled = await client.post(
            "/api/player/travel",
            json={"target_location_id": "castle", "expected_world_version": 2},
        )
        response = await client.post("/api/demo/reset")

    assert accepted.status_code == 200
    assert ticked.status_code == 200
    assert chatted.status_code == 200
    assert travelled.status_code == 200
    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": {
            "world_id": "aleria-town",
            "clock_tick": 0,
            "player_location_id": "tavern",
            "quest_status": "available",
        },
        "message": "Demo world reset",
    }

    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        world = session.get(WorldState, "aleria-town")
        ryan = session.get(NpcState, "ryan")
        player = session.get(PlayerState, "default-player")
        quest = session.get(
            QuestProgress,
            ("default-player", "missing-child"),
        )
        history_counts = {
            "actions": session.scalar(
                select(func.count()).select_from(WorldAction)
            ),
            "events": session.scalar(select(func.count()).select_from(Event)),
            "quest_events": session.scalar(
                select(func.count()).select_from(QuestEvent)
            ),
            "conversations": session.scalar(
                select(func.count()).select_from(Conversation)
            ),
            "messages": session.scalar(
                select(func.count()).select_from(ConversationMessage)
            ),
        }

    assert world is not None
    assert (world.day, world.time, world.clock_tick) == (1, "08:00", 0)
    assert ryan is not None
    assert (
        ryan.location_id,
        ryan.current_action,
        ryan.energy,
        ryan.mood,
        ryan.social,
    ) == ("park", "rest", 80, 78, 70)
    assert player is not None
    assert player.location_id == "tavern"
    assert quest is not None
    assert (
        quest.status,
        quest.version,
        quest.updated_clock_tick,
    ) == ("available", 0, 0)
    assert history_counts == {
        "actions": 0,
        "events": 0,
        "quest_events": 0,
        "conversations": 0,
        "messages": 0,
    }


def _add_cognition_graph(session, world_id: str, suffix: str) -> dict[str, str]:
    now = datetime.now(UTC)
    observation_id = str(uuid4())
    evidence_id = str(uuid4())
    reflection_id = str(uuid4())
    belief_id = str(uuid4())
    session.add(AgentCognitionState(
        world_id=world_id, owner_npc_id="grey", created_at=now, updated_at=now,
    ))
    session.add(Observation(
        id=observation_id, world_id=world_id, owner_npc_id="grey",
        source_kind="authored_knowledge", source_event_id=None,
        source_turn_id=None, source_user_message_id=None,
        source_assistant_message_id=None, source_key=f"test:{suffix}",
        policy_version="test-v1", occurred_world_version=0,
        occurred_clock_tick=0, occurred_world_time="08:00",
        source_created_at=now, created_at=now, perception_mode="participant",
        facts_json={}, related_entity_ids_json=[], summary="Test observation",
        secrecy="private", disclosure_scope="internal_only",
        lifecycle_state="active", is_critical=0,
    ))
    session.flush()
    common = dict(
        world_id=world_id, owner_npc_id="grey", content="Evidence",
        safe_summary="Safe evidence", normalized_content_hash="1" * 64,
        related_entity_ids_json=[], occurred_world_version=0,
        occurred_clock_tick=0, created_world_version=0, created_clock_tick=0,
        occurred_world_time="08:00", source_created_at=now, created_at=now,
        importance=0.5, confidence=0.5, emotional_valence=0,
        secrecy="private", disclosure_scope="internal_only",
        lifecycle_state="active", embedding_status="unavailable", access_count=0,
    )
    session.add(Memory(
        id=evidence_id, memory_type="episodic",
        source_observation_id=observation_id, authored_source_id=None,
        authored_source_version=None, **common,
    ))
    session.add(Memory(
        id=reflection_id, memory_type="reflection",
        source_observation_id=None, authored_source_id=None,
        authored_source_version=None, **common,
    ))
    session.flush()
    session.add(MemoryEvidence(
        derived_memory_id=reflection_id, evidence_memory_id=evidence_id, ordinal=0,
    ))
    session.add(Belief(
        id=belief_id, world_id=world_id, owner_npc_id="grey",
        statement="Test belief", safe_summary="Safe belief", confidence=0.5,
        lifecycle_state="active", supersedes_belief_id=None,
        source_reflection_memory_id=reflection_id, created_world_version=0,
        created_clock_tick=0, created_at=now,
    ))
    session.flush()
    session.add(BeliefEvidence(
        belief_id=belief_id, memory_id=evidence_id,
        evidence_role="supporting", ordinal=0,
    ))
    return {
        "observation": observation_id,
        "evidence": evidence_id,
        "reflection": reflection_id,
        "belief": belief_id,
    }


@pytest.mark.anyio
async def test_reset_clears_only_target_world_cognition_and_rebuilds_authored_knowledge_once(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        session.add(WorldState(
            id="other-world", name="Other", day=1, time="08:00",
            clock_tick=0, world_version=0, event_sequence=0,
        ))
        session.flush()
        _add_cognition_graph(session, "aleria-town", "target")
        other = _add_cognition_graph(session, "other-world", "other")
        session.commit()

    app = create_app(database_url, chat_provider=MockChatProvider())
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/demo/reset")

    assert response.status_code == 200
    with session_factory() as session:
        target_counts = {
            model.__tablename__: session.scalar(
                select(func.count()).select_from(model).where(model.world_id == "aleria-town")
            )
            for model in (AgentCognitionState, Observation, Memory, Belief)
        }
        authored = tuple(session.scalars(
            select(Memory)
            .where(Memory.world_id == "aleria-town", Memory.memory_type == "knowledge")
            .order_by(Memory.authored_source_id)
        ))
        target_evidence_count = session.scalar(
            select(func.count()).select_from(MemoryEvidence)
            .join(Memory, Memory.id == MemoryEvidence.derived_memory_id)
            .where(Memory.world_id == "aleria-town")
        )
        target_belief_evidence_count = session.scalar(
            select(func.count()).select_from(BeliefEvidence)
            .join(Belief, Belief.id == BeliefEvidence.belief_id)
            .where(Belief.world_id == "aleria-town")
        )

        assert session.get(Observation, other["observation"]) is not None
        assert session.get(Memory, other["evidence"]) is not None
        assert session.get(Memory, other["reflection"]) is not None
        assert session.get(Belief, other["belief"]) is not None
        assert session.get(AgentCognitionState, ("other-world", "grey")) is not None

    assert target_counts == {
        "agent_cognition_states": 0,
        "observations": 0,
        "memories": 3,
        "beliefs": 0,
    }
    assert target_evidence_count == 0
    assert target_belief_evidence_count == 0
    assert {memory.owner_npc_id for memory in authored} == {"ryan", "shir", "grey"}
    assert len({(memory.authored_source_id, memory.authored_source_version) for memory in authored}) == 3


def _add_agent_plan(session, world_id: str, npc_id: str, *, status: str = "active") -> str:
    """一条来自"上一个世界"的计划。内容刻意可辨认，便于确认它是否残留。"""
    plan_id = str(uuid4())
    session.add(AgentPlan(
        id=plan_id, world_id=world_id, owner_npc_id=npc_id, source_run_id=None,
        thought="stale thought", goal="stale goal", goal_reason="stale reason",
        steps_json=[{
            "action_type": "rest", "target_kind": None,
            "target_id": None, "intent": "stale step",
        }],
        current_step_index=0, status=status,
        created_clock_tick=7, updated_clock_tick=7,
        provider="fake", model="fake-planner-1", prompt_version="planning-v1",
        latency_ms=1, tokens_used=None, evidence_memory_ids_json=[],
    ))
    return plan_id


@pytest.mark.anyio
async def test_reset_clears_target_world_agent_plans_and_keeps_other_worlds(
    database_url,
    seed_dir,
):
    """Procedural memory 与其他认知数据同级：Reset 必须按 world 清干净，且只清目标世界。"""
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        session.add(WorldState(
            id="other-world", name="Other", day=1, time="08:00",
            clock_tick=0, world_version=0, event_sequence=0,
        ))
        session.flush()
        _add_agent_plan(session, "aleria-town", "ryan")
        _add_agent_plan(session, "aleria-town", "shir", status="completed")
        other_plan_id = _add_agent_plan(session, "other-world", "grey")
        session.commit()
        # 非空前提：目标世界确实有计划，否则下面的"已清空"断言什么也证明不了。
        assert session.scalar(
            select(func.count()).select_from(AgentPlan)
            .where(AgentPlan.world_id == "aleria-town")
        ) == 2

    app = create_app(database_url, chat_provider=MockChatProvider())
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/demo/reset")

    assert response.status_code == 200
    with session_factory() as session:
        target_plans = session.scalars(
            select(AgentPlan).where(AgentPlan.world_id == "aleria-town")
        ).all()
        surviving_other = session.get(AgentPlan, other_plan_id)

    assert [plan.goal for plan in target_plans] == []
    assert surviving_other is not None
    assert surviving_other.world_id == "other-world"


@pytest.mark.anyio
async def test_reset_lets_the_next_tick_replan_instead_of_reusing_a_stale_plan(
    database_url,
    seed_dir,
):
    """玩家可感知的后果：重置后的第一个 tick 必须重新规划，不能沿用上个世界的计划。"""
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    app = create_app(database_url, chat_provider=MockChatProvider())

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        for expected_version in range(3):
            ticked = await client.post(
                "/api/world/tick", json={"expected_world_version": expected_version}
            )
            assert ticked.status_code == 200

        # 非空前提：重置前确实存在活跃计划，否则"没有复用"是因为压根没得复用。
        with session_factory() as session:
            assert session.scalar(
                select(func.count()).select_from(AgentPlan)
                .where(AgentPlan.world_id == "aleria-town", AgentPlan.status == "active")
            ) > 0

        reset = await client.post("/api/demo/reset")
        assert reset.status_code == 200

        after = await client.post("/api/world/tick", json={"expected_world_version": 0})
        assert after.status_code == 200
        detail = await client.get(f"/api/agent-runs/{after.json()['data']['run']['id']}")

    assert detail.status_code == 200
    proposals = detail.json()["data"]["proposals"]
    assert len(proposals) == 3
    assert [p["source"] for p in proposals if p["source"] == "existing_plan"] == []
