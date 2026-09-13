import pytest
from sqlalchemy.exc import IntegrityError

from backend.app.agents.action_registry import ActionRegistry
from backend.app.agents.contracts import ActionProposal, ProposalSource
from backend.app.agents.orchestrator import run_advance, run_deterministic_advance
from backend.app.agents.planning_contracts import AgentDecision, PlanStep
from backend.app.database.plan_repository import PlanRepository
from tests.backend.test_golden_deterministic import build_golden_world


def _decision() -> AgentDecision:
    return AgentDecision(
        thought="体力不足", goal="恢复体力后回到岗位", goal_reason="能量低于阈值",
        steps=(
            PlanStep(action_type="eat", target_kind=None, target_id=None, intent="进食"),
            PlanStep(action_type="work", target_kind=None, target_id=None, intent="回到工作"),
        ),
        prompt_version="planning-v1",
    )


def test_partial_index_allows_only_one_active_plan_per_npc(plan_session, seeded_ids):
    """这是整个持久化层唯一会静默失败的地方：

    partial unique index 若没生效不会报错，只会悄悄允许一个 NPC 同时有多条活跃计划，
    导致 Planner 的 get_active 随机返回其中一条。必须显式验证索引真的生效。
    """
    world_id, npc_id = seeded_ids
    repo = PlanRepository(plan_session)

    first = repo.create_from_decision(
        world_id, npc_id, _decision(),
        clock_tick=5, run_id=None, provider="fake", model="fake-1", latency_ms=1, tokens_used=1,
    )
    plan_session.commit()
    assert first.status == "active", "非空前提：第一条计划确实处于 active"

    # 冲突可能在 create_from_decision 内部的 flush 抛出，也可能拖到 commit，
    # 两处都算索引生效，故一并纳入 raises 块。
    with pytest.raises(IntegrityError) as excinfo:
        repo.create_from_decision(
            world_id, npc_id, _decision(),
            clock_tick=6, run_id=None, provider="fake", model="fake-1", latency_ms=1, tokens_used=1,
        )
        plan_session.commit()
    # 必须是活跃计划唯一索引触发的，不能是外键 / NOT NULL 之类的顺带失败，
    # 否则这条测试证明不了索引本身生效。
    # 只看异常首行：完整消息里回显了 INSERT 语句，列名在那里恒出现，判别不了。
    # SQLite 报列名，PostgreSQL 报索引名，两种措辞都接受。
    first_line = str(excinfo.value).splitlines()[0]
    assert "uq_agent_plans_active" in first_line or (
        "UNIQUE constraint failed" in first_line
        and "world_id" in first_line
        and "owner_npc_id" in first_line
    ), str(excinfo.value)
    plan_session.rollback()

    # 反向验证：把第一条置为非活跃后，第二条必须能插入
    repo.abandon(repo.get_active(world_id, npc_id), clock_tick=7)
    plan_session.commit()
    repo.create_from_decision(
        world_id, npc_id, _decision(),
        clock_tick=8, run_id=None, provider="fake", model="fake-1", latency_ms=1, tokens_used=1,
    )
    plan_session.commit()
    assert repo.get_active(world_id, npc_id) is not None


def test_alias_keeps_backward_compatible_signature():
    """保护现有 11 处调用：不传 override 时行为必须与改造前完全一致。"""
    world = build_golden_world()
    assert run_deterministic_advance(world) == run_advance(world)
    assert run_deterministic_advance(world, registry=ActionRegistry(())) == run_advance(
        world, registry=ActionRegistry(())
    )


def test_rejected_llm_proposal_falls_back_and_world_still_advances():
    """spec §13 唯一不变量 —— 这是本项目最核心的卖点，必须有证据。"""
    world = build_golden_world()
    actor = world.npcs[0]
    unreachable = ActionProposal(
        actor_id=actor.id, action_type="move", target_kind="location",
        target_id="nowhere", reason_code="agent_plan", source=ProposalSource.LLM,
    )

    result = run_advance(world, proposal_override={actor.id: unreachable})

    assert result.world.world_version == world.world_version + 1, "世界必须推进"
    assert result.world.clock_tick == world.clock_tick + 1

    fallback = next(p for p in result.proposals if p.actor_id == actor.id)
    assert fallback.source is ProposalSource.FALLBACK

    accepted = [
        r for r in result.resolutions
        if r.proposal.actor_id == actor.id and r.validation.accepted
    ]
    assert accepted, "兜底提案必须通过校验并被执行"

    sources = [t.data.get("source") for t in result.traces if t.stage == "proposal"]
    assert sources, "非空前提：必须有 proposal 阶段的 trace"
    assert "fallback" in sources, "降级必须在 trace 中可见，否则 UI 无法显示徽章"
