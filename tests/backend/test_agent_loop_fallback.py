import pytest
from sqlalchemy.exc import IntegrityError

from backend.app.agents.planning_contracts import AgentDecision, PlanStep
from backend.app.database.plan_repository import PlanRepository


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
