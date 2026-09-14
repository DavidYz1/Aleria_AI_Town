from dataclasses import replace
import json
import threading

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from backend.app.agents.contracts import ProposalSource
from backend.app.agents.memory_retrieval import RetrievalResult
from backend.app.agents.planner import AgentPlanner
from backend.app.agents.planning_contracts import AgentDecision, PlanStep
from backend.app.database.models import AgentPlan
from backend.app.database.plan_repository import PlanRepository
from backend.app.llm.planning_provider import PlanningProviderError, PlanningRequest
from backend.app.world.action_rules import DEFAULT_ACTION_REGISTRY
from tests.backend.test_golden_deterministic import build_golden_world


def _kwargs():
    return {
        "thought": "体力偏低，先补充再出门",
        "goal": "补充体力后去广场打听消息",
        "goal_reason": "昨天玩家提到有孩子走失",
        "steps": (
            PlanStep(action_type="eat", target_kind=None, target_id=None, intent="进食"),
            PlanStep(action_type="move", target_kind="location", target_id="park", intent="前往广场"),
        ),
        "prompt_version": "planning-v1",
    }


def test_valid_decision_is_accepted():
    decision = AgentDecision(**_kwargs())
    assert len(decision.steps) == 2
    assert decision.steps[0].action_type == "eat"


def test_rejects_action_outside_the_six_verbs():
    """动作空间锁定为 6 个动词，模型不得发明新动作。

    走模型的真实路径验证。不能用 PlanStep.model_construct 造非法实例：
    那是 pydantic 显式的「跳过校验」逃生口，且 pydantic v2 默认
    revalidate_instances='never'，父模型不会重新校验已构造的子模型实例，
    那样写的测试无论实现对错都不会抛 ValidationError。
    """
    payload = {
        "thought": "体力偏低，先补充再出门",
        "goal": "补充体力后去广场打听消息",
        "goal_reason": "昨天玩家提到有孩子走失",
        "steps": [
            {"action_type": "craft", "target_kind": None, "target_id": None, "intent": "打造"}
        ],
        "prompt_version": "planning-v1",
    }

    # 路径 1：模型返回的 JSON 文本 —— Task 6 Live provider 的真实入口
    with pytest.raises(ValidationError):
        AgentDecision.model_validate_json(json.dumps(payload))

    # 路径 2：已解析为 dict 后构造
    with pytest.raises(ValidationError):
        AgentDecision(**payload)

    # 非空前提：同一份 payload 只把动词换成合法值必须通过。
    # 否则上面两条可能是别的字段出错才抛的异常，证明不了动作空间约束。
    legal = payload | {"steps": [payload["steps"][0] | {"action_type": "work"}]}
    assert AgentDecision.model_validate_json(json.dumps(legal)).steps[0].action_type == "work"


def test_rejects_empty_thought_and_oversized_plan():
    """两条边界合一：空 thought 与超过 4 步的计划都必须被拒。"""
    empty_thought = _kwargs() | {"thought": ""}
    with pytest.raises(ValidationError):
        AgentDecision(**empty_thought)

    step = PlanStep(action_type="rest", target_kind=None, target_id=None, intent="休息")
    oversized = _kwargs() | {"steps": (step,) * 5}
    with pytest.raises(ValidationError):
        AgentDecision(**oversized)


class StubProvider:
    provider_name = "stub"
    model_name = "stub-1"
    last_tokens_used = 42

    def __init__(self, decision=None, error=None):
        self.decision, self.error, self.calls = decision, error, 0

    def plan(self, request):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.decision


class StubRetriever:
    def retrieve(self, request):
        return RetrievalResult(memories=(), mode="stub")


def _plan_decision(*actions: str) -> AgentDecision:
    return AgentDecision(
        thought="测试推理", goal="测试目标", goal_reason="测试理由",
        steps=tuple(
            PlanStep(action_type=a, target_kind=None, target_id=None, intent=f"执行{a}")
            for a in actions
        ),
        prompt_version="planning-v1",
    )


def _planner(plan_session, provider, **kwargs):
    return AgentPlanner(
        PlanRepository(plan_session), StubRetriever(), provider, DEFAULT_ACTION_REGISTRY, **kwargs
    )


def test_active_plan_is_reused_without_calling_the_model(plan_session, seeded_ids):
    """spec §6 规则 2：有 active plan 时不调 LLM —— 这是成本控制的核心。"""
    provider = StubProvider(decision=_plan_decision("rest", "work"))
    planner = _planner(plan_session, provider)
    world = build_golden_world()
    actor = world.npcs[0]

    first = planner.decide(world, actor, last_outcome=None)
    plan_session.commit()
    assert provider.calls == 1
    assert first.source is ProposalSource.LLM
    assert first.proposal.action_type == "rest"

    second = planner.decide(world, actor, last_outcome=None)
    assert provider.calls == 1, "复用计划时不得再次调用模型"
    assert second.source is ProposalSource.EXISTING_PLAN
    assert second.proposal.action_type == "work"


def test_provider_failure_degrades_to_deterministic(plan_session, seeded_ids):
    """spec §13 唯一不变量：provider 失败仍产出可执行提案。"""
    planner = _planner(plan_session, StubProvider(error=PlanningProviderError("timeout")))
    world = build_golden_world()

    outcome = planner.decide(world, world.npcs[0], last_outcome=None)
    assert outcome.source is ProposalSource.FALLBACK
    assert outcome.proposal.action_type in {"move", "work", "eat", "talk", "rest", "wait"}
    assert outcome.plan is None


def test_plan_older_than_max_age_triggers_replanning(plan_session, seeded_ids):
    """spec §6 规则 5：过龄强制完成，防止 NPC 卡在一个计划里。"""
    provider = StubProvider(decision=_plan_decision("rest", "work", "eat"))
    planner = _planner(plan_session, provider, max_plan_age_ticks=2)
    world = build_golden_world()
    actor = world.npcs[0]

    planner.decide(world, actor, last_outcome=None)
    plan_session.commit()
    assert provider.calls == 1

    aged = replace(world, clock_tick=world.clock_tick + 5)
    outcome = planner.decide(aged, actor, last_outcome=None)
    assert provider.calls == 2, "过龄计划应被放弃并触发重新规划"
    assert outcome.source is ProposalSource.LLM


def test_planner_retrieval_never_writes_memory_access_telemetry(
    plan_session, seeded_ids, database_url,
):
    """Planner 的检索运行在 world tick 的事务内，且走**第二个** SQLite 连接。

    任何写入都拿不到写锁：它会干等满 sqlite3 的 5 秒 busy timeout 才失败，
    然后被 `MemoryRetriever` 的 telemetry try/except 静默吞掉。三个 NPC 就是
    16 秒一 tick，前端 5 秒超时，演示里每次推进都红字报错 —— 而世界其实推进了。

    实测：这条写入在该路径上**从未成功过**（access_count 恒为 0），
    所以禁止它不损失任何现有行为，只是不再为一次注定失败的写付 5.5 秒。
    """
    from backend.app.agents.memory_retrieval import MemoryRetriever
    from backend.app.database.cognition_repository import CognitionRepository
    from backend.app.database.connection import create_engine_and_session
    from backend.app.llm.embedding_provider import DeterministicEmbeddingProvider
    from backend.app.services.cognition_projection import CognitionProjectionService

    world_id, npc_id = seeded_ids
    embedding = DeterministicEmbeddingProvider()

    # 第二个连接，和 `api/dependencies.py:get_planner` 的装配方式一致。
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as cognition_session:
        cognition_repository = CognitionRepository(cognition_session)
        CognitionProjectionService(cognition_repository).catch_up_world(world_id)
        cognition_session.commit()

        request_log: list = []

        class RecordingRepository(CognitionRepository):
            def record_access(self, memory_ids):
                request_log.append(tuple(memory_ids))
                return super().record_access(memory_ids)

        recording = RecordingRepository(cognition_session)
        candidates = recording.allowed_memories(
            _retrieval_request_for(world_id, npc_id)
        )
        cognition_session.rollback()
        # 非空前提：owner 确实有可检索的记忆，否则「没写 telemetry」是平凡成立的。
        assert candidates, "投影后 owner 必须有可检索记忆，否则本测试证明不了任何事"

        planner = AgentPlanner(
            PlanRepository(plan_session),
            MemoryRetriever(recording, embedding),
            StubProvider(decision=_plan_decision("rest", "work")),
            DEFAULT_ACTION_REGISTRY,
        )
        world = replace(build_golden_world(), id=world_id)
        actor = next(npc for npc in world.npcs if npc.id == npc_id)

        # tick session 持有事务 —— 这正是 WorldTickService.advance 调 _plan 时的状态。
        plan_session.execute(select(AgentPlan).limit(1))
        assert plan_session.in_transaction(), "非空前提：tick session 必须正持有事务"

        outcome = planner.decide(world, actor, last_outcome=None)

    assert outcome.source is ProposalSource.LLM
    assert request_log == [], (
        f"planner 检索不得写 access telemetry，实际尝试写入 {request_log}"
    )


def _retrieval_request_for(world_id: str, npc_id: str):
    from backend.app.agents.memory_retrieval import (
        MemoryType,
        RetrievalRequest,
        RetrievalScope,
    )

    return RetrievalRequest(
        world_id=world_id, owner_npc_id=npc_id,
        current_world_version=1, current_clock_tick=1,
        query_text="knight 当前处境与近期经历",
        scope=RetrievalScope.INTERNAL_REFLECTION,
        allowed_memory_types=frozenset(MemoryType),
        limit=6, char_budget=1200,
    )


def test_configured_provider_timeout_survives_a_request_that_does_not_narrow_it():
    """`PLANNING_PROVIDER_TIMEOUT_SECONDS` 必须真的到达出站请求。

    `AgentPlanner` 不传 `timeout_seconds`，provider 又取 `min(配置, 请求)`。
    只要请求端有个非 None 的默认值，配置就被它悄悄压掉 —— 没有异常、没有日志，
    只是每次调用都在更短的时限上超时，然后一路降级到确定性兜底。
    实测该模型单次规划要 7.6–17 秒，被压到 8 秒就等于 Live 规划永远不可用。
    """
    import httpx

    from backend.app.llm.planning_provider import OpenAICompatiblePlanningProvider

    recorded: list[float | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded.append(request.extensions.get("timeout", {}).get("read"))
        return httpx.Response(200, json={"choices": [{"message": {"tool_calls": [
            {"function": {"name": "rest", "arguments": json.dumps({
                "reason_code": "low_energy", "intent": "休息",
                "thought": "体力偏低", "goal": "恢复体力", "goal_reason": "低于阈值"})}}]}}]})

    provider = OpenAICompatiblePlanningProvider(
        base_url="https://api.example.com/v1", api_key="k", model="m",
        auth_mode="bearer", timeout_seconds=25,
        transport=httpx.MockTransport(handler),
    )
    manifest = DEFAULT_ACTION_REGISTRY.to_tool_manifest()

    provider.plan(PlanningRequest(npc_id="ryan", context_text="x", tool_manifest=manifest))
    assert recorded == [25], f"未指定超时的请求必须沿用配置值 25s，实际 {recorded}"

    # 请求仍然可以收紧超时；能收紧才证明上面那条不是「干脆忽略请求」。
    provider.plan(PlanningRequest(
        npc_id="ryan", context_text="x", tool_manifest=manifest, timeout_seconds=4))
    assert recorded == [25, 4], f"请求显式给出的更短超时必须生效，实际 {recorded}"


class BarrierProvider:
    """两道 barrier，两条断言各自确定性成立，不依赖任何计时阈值。

    `arrival`：三个 NPC 的规划必须**同时**在途才放行。串行实现下第一次调用
    永远等不到另外两个，barrier 超时抛 `BrokenBarrierError`。

    `written`：三个线程都写完自己的 token 之后才允许任何一个返回。
    provider 若用共享属性存 token（而不是 thread-local），三个线程读到的就都是
    最后一个写入者的数字 —— 于是 token 归属错位被**必然**暴露，而不是碰运气。
    """

    provider_name = "barrier"
    model_name = "barrier-1"

    def __init__(self, parties: int):
        self.arrival = threading.Barrier(parties, timeout=5)
        self.written = threading.Barrier(parties, timeout=5)
        self._state = threading.local()
        self.threads: set[int] = set()

    @staticmethod
    def tokens_for(npc_id: str) -> int:
        return 100 + sum(npc_id.encode())

    @property
    def last_tokens_used(self):
        return getattr(self._state, "tokens", None)

    def plan(self, request):
        self.threads.add(threading.get_ident())
        self.arrival.wait()
        self._state.tokens = self.tokens_for(request.npc_id)
        self.written.wait()
        return AgentDecision(
            thought=f"{request.npc_id} 的推理", goal=f"{request.npc_id} 的目标",
            goal_reason=f"{request.npc_id} 的理由",
            steps=(PlanStep(action_type="rest", target_kind=None, target_id=None,
                            intent=f"{request.npc_id} 休息"),),
            prompt_version="planning-v1",
        )


def test_provider_calls_run_concurrently_and_stay_attributed_to_their_own_npc(
    plan_session, seeded_ids,
):
    world = build_golden_world()
    provider = BarrierProvider(len(world.npcs))
    planner = _planner(plan_session, provider)

    outcomes = planner.decide_many(world, world.npcs, last_outcome=None)
    plan_session.commit()

    # 非空前提：三个 NPC 都真的走了模型分支，否则两道 barrier 根本不会被触及。
    assert len(outcomes) == len(world.npcs) == 3
    assert all(o.source is ProposalSource.LLM for o in outcomes.values())
    assert len(provider.threads) == 3, f"三次调用应落在三个线程上，实际 {len(provider.threads)}"

    # 三个 token 两两不同，才谈得上「错位会被看见」。
    expected = {npc.id: BarrierProvider.tokens_for(npc.id) for npc in world.npcs}
    assert len(set(expected.values())) == 3

    for npc in world.npcs:
        outcome = outcomes[npc.id]
        assert outcome.plan.goal == f"{npc.id} 的目标", "计划串到了别的 NPC 头上"
        assert outcome.plan.thought == f"{npc.id} 的推理"
        assert outcome.tokens_used == expected[npc.id], "token 归属错位"
        assert outcome.plan.tokens_used == expected[npc.id]


def test_one_failing_npc_does_not_take_down_the_others(plan_session, seeded_ids):
    """spec §13 不变量在并发下依然成立：单个 NPC 失败只影响它自己。"""
    world = build_golden_world()
    failing = world.npcs[1].id

    class PartiallyFailing:
        provider_name, model_name, last_tokens_used = "partial", "partial-1", None

        def plan(self, request):
            if request.npc_id == failing:
                raise PlanningProviderError("timeout")
            return _plan_decision("rest")

    outcomes = _planner(plan_session, PartiallyFailing()).decide_many(
        world, world.npcs, last_outcome=None)
    plan_session.commit()

    assert outcomes[failing].source is ProposalSource.FALLBACK
    assert outcomes[failing].plan is None
    survivors = [npc.id for npc in world.npcs if npc.id != failing]
    # 非空前提：确实有幸存者，否则「只影响它自己」无从谈起。
    assert survivors and all(outcomes[i].source is ProposalSource.LLM for i in survivors)


def test_decide_many_reuses_active_plans_without_calling_the_model(plan_session, seeded_ids):
    """复用分支不得进入线程池 —— 它只有数据库操作，跑并发只会制造 Session 竞争。"""
    world = build_golden_world()
    provider = StubProvider(decision=_plan_decision("rest", "work"))
    planner = _planner(plan_session, provider)

    planner.decide_many(world, world.npcs, last_outcome=None)
    plan_session.commit()
    assert provider.calls == 3

    second = planner.decide_many(world, world.npcs, last_outcome=None)
    plan_session.commit()
    assert provider.calls == 3, "有活跃计划时不得再次调用模型"
    assert all(o.source is ProposalSource.EXISTING_PLAN for o in second.values())
