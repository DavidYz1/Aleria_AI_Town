"""The evaluator must report measured calls without inventing failure causes."""

import json
import sys

from backend.app.llm.planning_provider import FakePlanningProvider, PlanningProviderError
from scripts import eval_agent


def test_metered_provider_keeps_failed_calls_in_the_denominator():
    class FailingProvider(FakePlanningProvider):
        def plan(self, request):
            raise PlanningProviderError("planning unavailable")

    meter = eval_agent.MeteredPlanningProvider(FailingProvider())
    meter.begin_tick(1)
    from backend.app.llm.planning_provider import PlanningRequest

    try:
        meter.plan(PlanningRequest(npc_id="ryan", context_text="world"))
    except PlanningProviderError:
        pass
    else:
        raise AssertionError("provider should fail")

    assert len(meter.samples) == 1
    # 这个替身抛的是不带 reason 的 PlanningProviderError（真实 adapter 现在总会
    # 带上分类）。拿不到分类时只能记 "unknown" —— 不按异常长相猜一个更具体的。
    assert meter.samples[0].failure_reason == "unknown"
    assert meter.samples[0].duration_ms >= 0


def test_fake_eval_counts_reused_steps_and_every_npc_tick(database_url, seed_dir):
    from scripts.eval_agent import collect, run_ticks
    from scripts.seed_world import seed_database

    seed_database(database_url, seed_dir)
    meter = eval_agent.MeteredPlanningProvider(FakePlanningProvider())
    durations = run_ticks(database_url, 4, meter)
    stats = collect(database_url, meter.samples)

    assert len(durations) == 4
    assert stats["proposals"] == 12
    assert stats["provider_calls"] == len(meter.samples)
    assert stats["reuse"] > 0
    assert stats["fallback_reasons"] == {}
    assert stats["call_success"] == stats["provider_calls"]
    evidence = eval_agent.build_evidence(stats, durations, meter.samples)
    assert evidence["counts"]["provider_calls"] == len(meter.samples)
    assert len(evidence["tick_durations_seconds"]) == 4
    assert len(evidence["call_samples"]) == len(meter.samples)
    assert all("context_text" not in sample for sample in evidence["call_samples"])


def test_generic_provider_failure_is_not_reported_as_schema_or_timeout(database_url, seed_dir):
    from scripts.eval_agent import collect, run_ticks
    from scripts.seed_world import seed_database

    class FailingProvider(FakePlanningProvider):
        def plan(self, request):
            raise PlanningProviderError("planning unavailable")

    seed_database(database_url, seed_dir)
    meter = eval_agent.MeteredPlanningProvider(FailingProvider())
    run_ticks(database_url, 1, meter)
    stats = collect(database_url, meter.samples)

    assert stats["provider_calls"] == 3
    assert stats["fallback"] == 3
    # 归因现在来自落盘的 planning trace（`<stage>:<code>`），不再从 source 反推。
    assert stats["fallback_reasons"] == {"provider:unknown": 3}


def test_rule_rejection_has_separate_fallback_reason(database_url, seed_dir):
    from backend.app.agents.planning_contracts import PlanStep
    from scripts.eval_agent import collect, run_ticks
    from scripts.seed_world import seed_database

    class RejectedProvider(FakePlanningProvider):
        def plan(self, request):
            decision = super().plan(request)
            return decision.model_copy(update={
                "steps": (PlanStep(
                    action_type="move", target_kind="location",
                    target_id="not-a-location", intent="try invalid target",
                ),)
            })

    seed_database(database_url, seed_dir)
    meter = eval_agent.MeteredPlanningProvider(RejectedProvider())
    run_ticks(database_url, 1, meter)
    stats = collect(database_url, meter.samples)

    assert stats["call_success"] == 3
    assert stats["fallback"] == 3
    # 规则拒绝现在带具体拒绝码：目标地点不存在。
    assert stats["fallback_reasons"] == {"rule:unknown_location": 3}


def test_fake_cli_clears_keyless_live_provider_configuration(monkeypatch, tmp_path):
    monkeypatch.setenv("PLANNING_PROVIDER_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("PLANNING_PROVIDER_MODEL", "synthetic")
    monkeypatch.setenv("PLANNING_PROVIDER_AUTH_MODE", "none")
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    monkeypatch.setattr(eval_agent.tempfile, "mkdtemp", lambda **_kwargs: str(scratch))
    monkeypatch.setattr(sys, "argv", ["eval_agent.py", "--ticks", "1", "--provider", "fake",
                                  "--out", str(tmp_path / "report.md")])

    assert eval_agent.main() == 0
    assert not eval_agent.os.environ["PLANNING_PROVIDER_BASE_URL"]
    assert not eval_agent.os.environ["PLANNING_PROVIDER_MODEL"]
    assert eval_agent.os.environ["PLANNING_PROVIDER_AUTH_MODE"] == "bearer"
    assert not scratch.exists(), "isolated database should be removed after evaluation"
    evidence = json.loads((tmp_path / "report.evidence.json").read_text(encoding="utf-8"))
    assert evidence["counts"]["proposals"] == 3
    assert len(evidence["call_samples"]) == 3
    assert "context_text" not in (tmp_path / "report.evidence.json").read_text(encoding="utf-8")
