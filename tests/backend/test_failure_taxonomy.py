"""兜底原因必须可归因到「谁拒绝的」和「拒绝码是什么」。

背景：2026-09-16 的 Live 探路只能报出「兜底 5 次」，其中 2 次 `provider_unknown`、
3 次 `rule_rejected`。前者的超时 / HTTP / 解析错误在 adapter 里被合并成同一个异常；
后者的拒绝码在 `orchestrator._with_fallback` 里被 `.accepted` 丢弃，且原始提案被整体
替换，所以落盘的 proposal / validation trace 记录的都是**替换后**的兜底动作。

这些测试锁定两件事：失败分类不被丢弃，以及被替换掉的原始提案仍然可追溯。
"""

import json

import httpx
import pytest

from backend.app.llm.planning_provider import (
    OpenAICompatiblePlanningProvider,
    PlanningProviderError,
    PlanningRequest,
)
from backend.app.world.action_rules import DEFAULT_ACTION_REGISTRY


def _provider(handler, **kwargs) -> OpenAICompatiblePlanningProvider:
    return OpenAICompatiblePlanningProvider(
        base_url="https://api.example.com/v1", api_key="k", model="m",
        auth_mode="bearer", timeout_seconds=kwargs.pop("timeout_seconds", 25),
        transport=httpx.MockTransport(handler),
    )


def _request() -> PlanningRequest:
    return PlanningRequest(
        npc_id="ryan", context_text="x",
        tool_manifest=DEFAULT_ACTION_REGISTRY.to_tool_manifest(),
    )


def _valid_payload() -> dict:
    return {"choices": [{"message": {"tool_calls": [
        {"function": {"name": "rest", "arguments": json.dumps({
            "reason_code": "low_energy", "intent": "休息",
            "thought": "体力偏低", "goal": "恢复体力", "goal_reason": "低于阈值"})}}]}}]}


def test_http_status_error_is_classified_as_http_status():
    """服务端明确拒绝（401/429/500）与「根本没连上」是两种排障方向，不能混。"""
    provider = _provider(lambda request: httpx.Response(500, json={"error": "boom"}))

    with pytest.raises(PlanningProviderError) as excinfo:
        provider.plan(_request())

    assert excinfo.value.reason == "http_status"


def test_transport_error_is_classified_as_transport():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    provider = _provider(handler)

    with pytest.raises(PlanningProviderError) as excinfo:
        provider.plan(_request())

    assert excinfo.value.reason == "transport"


def test_unparseable_response_is_classified_as_parse_error():
    """返回了 200 和 JSON，但不是我们要的结构 —— 这既不是超时也不是 HTTP 错误。"""
    provider = _provider(lambda request: httpx.Response(200, json={"choices": []}))

    with pytest.raises(PlanningProviderError) as excinfo:
        provider.plan(_request())

    assert excinfo.value.reason == "parse_error"


def test_timeout_is_classified_as_timeout():
    """超时必须能与上面三类区分 —— 这正是旧报告「19 次超时」无法复核的原因。"""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("read timed out", request=request)

    provider = _provider(handler)

    with pytest.raises(PlanningProviderError) as excinfo:
        provider.plan(_request())

    assert excinfo.value.reason == "timeout"


def test_successful_call_still_returns_a_decision():
    """非空前提：上面四条断言的是失败分类，这条确认正常路径没被改坏。"""
    provider = _provider(lambda request: httpx.Response(200, json=_valid_payload()))

    decision = provider.plan(_request())

    assert decision.steps[0].action_type == "rest"


def _planning_traces(database_url: str) -> list[dict]:
    """读回落盘的 planning trace，按 tick 顺序。"""
    from sqlalchemy import select

    from backend.app.database.connection import create_engine_and_session
    from backend.app.database.models import AgentTraceEntry

    engine, session_factory = create_engine_and_session(database_url)
    try:
        with session_factory() as session:
            return [
                entry.data_json
                for entry in session.scalars(
                    select(AgentTraceEntry).where(AgentTraceEntry.stage == "planning")
                )
            ]
    finally:
        engine.dispose()


def _run_one_tick(database_url: str, seed_dir, provider) -> None:
    from scripts.eval_agent import run_ticks
    from scripts.seed_world import seed_database

    seed_database(database_url, seed_dir)
    run_ticks(database_url, 1, provider)


def test_provider_failure_reason_reaches_the_planning_trace(database_url, seed_dir):
    """分类必须一路走到落盘，否则评测仍然只能推断。

    链路：provider 抛出带 reason 的错误 → planner._ask 捕获 → PlanningOutcome
    → world_clock_service._planning_trace → agent_trace_entries.data_json。
    中间任何一层丢掉 reason，这条就红。
    """
    from backend.app.llm.planning_provider import FakePlanningProvider

    class TimingOutProvider(FakePlanningProvider):
        def plan(self, request):
            raise PlanningProviderError("planning unavailable", reason="timeout")

    _run_one_tick(database_url, seed_dir, TimingOutProvider())
    traces = _planning_traces(database_url)

    assert len(traces) == 3, f"非空前提：三个 NPC 各有一条 planning trace，实际 {len(traces)}"
    assert all(item["source"] == "fallback" for item in traces), traces
    assert all(item["failure_stage"] == "provider" for item in traces), traces
    assert all(item["failure_code"] == "timeout" for item in traces), traces


def test_successful_planning_records_no_failure_fields(database_url, seed_dir):
    """负向对照：成功的规划不得带上失败分类，否则上面那条测的是常量。"""
    from backend.app.llm.planning_provider import FakePlanningProvider

    _run_one_tick(database_url, seed_dir, FakePlanningProvider())
    traces = _planning_traces(database_url)

    assert len(traces) == 3, f"非空前提：三条 planning trace，实际 {len(traces)}"
    assert all(item["source"] == "llm" for item in traces), traces
    assert all(item["failure_stage"] is None for item in traces), traces
    assert all(item["failure_code"] is None for item in traces), traces


def _traces_of_stage(database_url: str, stage: str) -> list[tuple[str | None, dict]]:
    from sqlalchemy import select

    from backend.app.database.connection import create_engine_and_session
    from backend.app.database.models import AgentTraceEntry

    engine, session_factory = create_engine_and_session(database_url)
    try:
        with session_factory() as session:
            return [
                (entry.actor_id, entry.data_json)
                for entry in session.scalars(
                    select(AgentTraceEntry).where(AgentTraceEntry.stage == stage)
                )
            ]
    finally:
        engine.dispose()


def test_rule_rejection_records_the_replaced_proposal(database_url, seed_dir):
    """被规则拒绝的原始提案必须留痕，否则「3 次 rule_rejected」无法定位。

    `orchestrator._with_fallback` 在提案进入 `resolve_proposals` 之前就把它整体
    换成了确定性兜底，所以 proposal / validation trace 记录的都是**替换后**的动作，
    validation 的 code 甚至是 `accepted`。原始动作与拒绝码两者都没有落盘。
    """
    from backend.app.agents.planning_contracts import PlanStep
    from backend.app.llm.planning_provider import FakePlanningProvider

    class InvalidLocationProvider(FakePlanningProvider):
        def plan(self, request):
            decision = super().plan(request)
            return decision.model_copy(update={"steps": (PlanStep(
                action_type="move", target_kind="location",
                target_id="not-a-location", intent="走向一个不存在的地点"),)})

    _run_one_tick(database_url, seed_dir, InvalidLocationProvider())
    rejections = _traces_of_stage(database_url, "rule_rejection")

    assert len(rejections) == 3, f"三个 NPC 各被拒一次，实际 {len(rejections)}"
    for actor_id, data in rejections:
        assert actor_id is not None
        assert data["failure_stage"] == "rule"
        assert data["failure_code"] == "unknown_location", data
        assert data["attempted_action"] == "move", data
        assert data["attempted_target"] == {"kind": "location", "id": "not-a-location"}, data
        assert data["attempted_source"] == "llm", data


def test_accepted_proposals_leave_no_rule_rejection_trace(database_url, seed_dir):
    """负向对照：动作合法时不得凭空产生拒绝记录。"""
    from backend.app.llm.planning_provider import FakePlanningProvider

    _run_one_tick(database_url, seed_dir, FakePlanningProvider())

    assert _traces_of_stage(database_url, "proposal"), "非空前提：本 tick 确实产生了提案"
    assert _traces_of_stage(database_url, "rule_rejection") == []


def test_public_run_detail_exposes_rule_rejection_without_the_attempted_target(
    database_url, seed_dir
):
    """公开投影：落盘完整、对外收窄 —— 与 `npc_plan` 的 evidence 同一条规则。

    `failure_code` / `attempted_action` 是枚举出来的类别名，公开它们让「NPC 为什么
    忽然按确定性策略行动」有据可依。`attempted_target.id` 不同：它是模型编造的自由
    文本，不进公开响应。

    同时这条也守住 README 的披露原则 —— 不可公开的内容**不以空条目或占位符出现**。
    rule_rejection 若不在投影白名单里，它会退化成一条 `data={}` 的空条目，那正是
    「以占位符暴露差额」。
    """
    from backend.app.agents.planning_contracts import PlanStep
    from backend.app.llm.planning_provider import FakePlanningProvider
    from fastapi.testclient import TestClient

    from backend.app.main import create_app

    class InvalidLocationProvider(FakePlanningProvider):
        def plan(self, request):
            decision = super().plan(request)
            return decision.model_copy(update={"steps": (PlanStep(
                action_type="move", target_kind="location",
                target_id="not-a-location", intent="走向一个不存在的地点"),)})

    _run_one_tick(database_url, seed_dir, InvalidLocationProvider())

    app = create_app(database_url=database_url)
    with TestClient(app) as client:
        run_id = client.get("/api/world").json()["data"]["world"]["id"]
        # 取最近一次 run：world 响应里没有 run id，改从 trace 表回读。
        from sqlalchemy import select

        from backend.app.database.connection import create_engine_and_session
        from backend.app.database.models import AgentTraceEntry

        engine, session_factory = create_engine_and_session(database_url)
        try:
            with session_factory() as session:
                run_id = session.scalars(
                    select(AgentTraceEntry.run_id).where(
                        AgentTraceEntry.stage == "rule_rejection"
                    )
                ).first()
        finally:
            engine.dispose()
        assert run_id is not None, "非空前提：本 tick 确实产生了规则拒绝"
        response = client.get(f"/api/agent-runs/{run_id}")

    assert response.status_code == 200
    items = [
        item for item in response.json()["data"]["trace"]
        if item["stage"] == "rule_rejection"
    ]
    assert len(items) == 3, f"三条拒绝记录都应出现，实际 {len(items)}"
    for item in items:
        assert item["data"], "非空前提：不能退化成 data={} 的空条目"
        assert item["data"]["failure_stage"] == "rule"
        assert item["data"]["failure_code"] == "unknown_location"
        assert item["data"]["attempted_action"] == "move"
        assert "attempted_target" not in item["data"], item["data"]
    assert "not-a-location" not in response.text


def test_evaluation_reads_persisted_reasons_instead_of_inferring(database_url, seed_dir):
    """评测必须直接读落盘分类，而不是从 source 反推。

    旧实现靠「planning 说 llm、executed 说 fallback」推断出 `rule_rejected`。推断
    结论是对的，但拿不到任何细节 —— 报告只能写「3 次规则拒绝」，答不出是哪条规则。
    """
    from backend.app.agents.planning_contracts import PlanStep
    from backend.app.llm.planning_provider import FakePlanningProvider
    from scripts.eval_agent import MeteredPlanningProvider, collect, run_ticks
    from scripts.seed_world import seed_database

    class InvalidLocationProvider(FakePlanningProvider):
        def plan(self, request):
            decision = super().plan(request)
            return decision.model_copy(update={"steps": (PlanStep(
                action_type="move", target_kind="location",
                target_id="not-a-location", intent="走向一个不存在的地点"),)})

    seed_database(database_url, seed_dir)
    meter = MeteredPlanningProvider(InvalidLocationProvider())
    run_ticks(database_url, 1, meter)
    stats = collect(database_url, meter.samples)

    assert stats["fallback"] == 3, "非空前提：三次兜底确实发生了"
    assert stats["fallback_reasons"] == {"rule:unknown_location": 3}


def test_evaluation_separates_provider_reasons_by_kind(database_url, seed_dir):
    """provider 侧的四类必须各自成列，不再统称 unknown。"""
    from backend.app.llm.planning_provider import FakePlanningProvider
    from scripts.eval_agent import MeteredPlanningProvider, collect, run_ticks
    from scripts.seed_world import seed_database

    class TimingOutProvider(FakePlanningProvider):
        def plan(self, request):
            raise PlanningProviderError("planning unavailable", reason="timeout")

    seed_database(database_url, seed_dir)
    meter = MeteredPlanningProvider(TimingOutProvider())
    run_ticks(database_url, 1, meter)
    stats = collect(database_url, meter.samples)

    assert stats["fallback"] == 3
    assert stats["fallback_reasons"] == {"provider:timeout": 3}
    assert meter.samples[0].failure_reason == "timeout", "计量侧也应拿到具体分类"
