"""Stage 3m Agent Evaluation：离线跑 N tick，输出 markdown 指标表。

隔离原则：每次运行都新建一个临时 SQLite 数据库并迁移到 head，
**绝不打开 `backend/data/aleria.db`**。

指标使用两种数据源，不复算业务逻辑：
- 临时库的 planning/proposal trace、agent_plans、actions 给出计划来源、规则替换、
  计划状态和行为分布；
- 进程内计量给出每次 Provider 调用与 tick 的耗时、token 覆盖和可观察失败。
指定 `--out` 时，这些去内容化原始样本同时写入 `.evidence.json`，可审阅报告分母。
既有 trace 不能区分 Live adapter 合并后的超时、HTTP 错误与响应解析失败。

用法：
    python scripts/eval_agent.py --ticks 20 --provider fake
    python scripts/eval_agent.py --ticks 20 --provider live --out docs/eval/report.md
"""
import argparse
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import time


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import select

from backend.app.core.config import Settings, get_settings
from backend.app.database.connection import create_engine_and_session
from backend.app.database.models import AgentPlan, AgentRun, AgentTraceEntry, WorldAction
from backend.app.llm.embedding_provider import DeterministicEmbeddingProvider
from backend.app.llm.planning_provider import (
    FakePlanningProvider,
    OpenAICompatiblePlanningProvider,
    build_planning_provider,
    classify_planning_failure,
)
from backend.app.llm.reflection_provider import FakeReflectionProvider
from backend.app.world.action_rules import DEFAULT_ACTION_REGISTRY
from scripts.seed_world import seed_database


MODEL_AUTHORED = ("llm", "existing_plan")
BEHAVIOUR_COLLAPSE_THRESHOLD = 1.0
KEY_ENV_VARS = (
    "CHAT_LLM_API_KEY", "EMBEDDING_API_KEY", "REFLECTION_API_KEY",
    "PLANNING_PROVIDER_API_KEY",
)
SAFE_PROVIDER_ENV = {
    "CHAT_PROVIDER": "mock",
    "CHAT_LLM_BASE_URL": "", "CHAT_LLM_MODEL": "", "CHAT_LLM_AUTH_MODE": "bearer",
    "EMBEDDING_PROVIDER": "fake",
    "EMBEDDING_BASE_URL": "", "EMBEDDING_MODEL": "", "EMBEDDING_AUTH_MODE": "bearer",
    "REFLECTION_PROVIDER": "fake",
    "REFLECTION_BASE_URL": "", "REFLECTION_MODEL": "", "REFLECTION_AUTH_MODE": "bearer",
    "PLANNING_PROVIDER_BASE_URL": "", "PLANNING_PROVIDER_MODEL": "",
    "PLANNING_PROVIDER_AUTH_MODE": "bearer",
}


def _isolate_provider_environment() -> None:
    Settings.model_config["env_file"] = None
    for name in KEY_ENV_VARS:
        os.environ[name] = ""
    os.environ.update(SAFE_PROVIDER_ENV)
    get_settings.cache_clear()


@dataclass(frozen=True)
class CallSample:
    tick: int
    npc_id: str
    duration_ms: float
    decision_ok: bool
    tokens_used: int | None
    failure_reason: str | None


class MeteredPlanningProvider:
    """Record actual attempts, including failures absent from agent_plans.

    The adapter still raises a single PlanningProviderError type, but it now carries
    a `reason`. We read that reason rather than guessing from the exception's shape;
    anything without one falls back to exception-type classification, and failing
    that, "unknown" — never a fabricated timeout or schema failure.
    """

    def __init__(self, provider):
        self._provider = provider
        self.provider_name = provider.provider_name
        self.model_name = provider.model_name
        self._tick = 0
        self._samples: list[CallSample] = []
        self._lock = threading.Lock()

    @property
    def last_tokens_used(self) -> int | None:
        return getattr(self._provider, "last_tokens_used", None)

    @property
    def samples(self) -> tuple[CallSample, ...]:
        with self._lock:
            return tuple(self._samples)

    def begin_tick(self, tick: int) -> None:
        with self._lock:
            self._tick = tick

    def plan(self, request):
        # The adapter stores usage per calling thread. Clear it so a failed call
        # cannot inherit the previous successful call's token count.
        if hasattr(self._provider, "last_tokens_used"):
            self._provider.last_tokens_used = None
        started = time.monotonic()
        ok, reason = False, None
        try:
            decision = self._provider.plan(request)
            ok = True
            return decision
        except Exception as exc:
            # 优先用 provider 自己给出的分类；它没给（非 PlanningProviderError 的
            # 意外异常）才按异常类型判，判不出就是 unknown —— 绝不臆造。
            reason = getattr(exc, "reason", None) or classify_planning_failure(exc)
            raise
        finally:
            tokens = self.last_tokens_used
            with self._lock:
                self._samples.append(CallSample(
                    self._tick, request.npc_id,
                    (time.monotonic() - started) * 1000, ok,
                    tokens if isinstance(tokens, int) and not isinstance(tokens, bool) else None,
                    reason,
                ))


def percentile(values: list[float], fraction: float) -> float | None:
    """Nearest-rank percentile; no interpolation of a small tick sample."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[math.ceil(fraction * len(ordered)) - 1]


def shannon_entropy(counts) -> float:
    total = sum(counts)
    if total == 0:
        return 0.0
    return -sum((n / total) * math.log2(n / total) for n in counts if n)


# `<stage>:<code>` 的中文说明。未收录的 code 直接原样显示 —— 宁可露出一个陌生的
# 英文码，也不要用一个笼统的中文标签把它盖掉。
FAILURE_STAGE_LABELS = {"provider": "Provider", "rule": "规则"}
FAILURE_CODE_LABELS = {
    # provider 侧：adapter 按异常类型分的四类
    "timeout": "调用超时", "http_status": "HTTP 状态错误",
    "transport": "连接失败", "parse_error": "响应结构无效",
    "unknown": "原因未区分",
    # rule 侧：ActionRegistry 与 conflict_resolver 的拒绝码
    "unknown_action": "动作不存在", "actor_mismatch": "提案者与状态不符",
    "invalid_target": "目标参数不合法", "unknown_location": "目标地点不存在",
    "wrong_duty_location": "不在本职岗位", "not_at_tavern": "不在酒馆",
    "talk_target_unavailable": "交谈对象不在同地点",
    "unknown_actor": "提案者不在世界快照中",
    "duplicate_actor_proposal": "同一 NPC 重复提案",
    "validator_error": "校验器自身异常",
}


def describe_failure(reason: str) -> str:
    """把 `<stage>:<code>` 渲染成人读得懂的一行，未知 code 原样保留。"""
    stage, _, code = reason.partition(":")
    if not code:
        return reason
    return (
        f"{FAILURE_STAGE_LABELS.get(stage, stage)}·"
        f"{FAILURE_CODE_LABELS.get(code, code)}（`{reason}`）"
    )


def _percent(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "—（样本为 0）"
    return f"{numerator / denominator:.1%}（{numerator}/{denominator}）"


def remove_workspace(workspace: Path) -> None:
    """删除隔离库目录；删不掉要说出来，不要静默留下文件。

    静默的 `ignore_errors=True` 曾经掩盖过一个真实缺陷：seed / TestClient /
    collect 三处 engine 都没 dispose，Windows 始终占着 SQLite 文件，于是每跑一次
    评测就在临时目录里积一个库，而「用完即删的隔离库」这个承诺看起来仍然成立。
    """
    try:
        shutil.rmtree(workspace)
    except OSError as exc:
        print(f"警告：未能删除隔离库 {workspace}：{exc}", file=sys.stderr)


def run_ticks(database_url: str, ticks: int, planning_provider,
              settings: Settings | None = None) -> list[float]:
    """真实跑 `POST /api/world/tick`，走和游戏完全相同的路由与持久化路径。

    Embedding 与 Reflection 一律注入替身：本脚本评估的是规划回路，
    让 live reflection 一起跑只会在每 tick 上叠加十几秒与额外开销，
    并不改变任何一项指标。
    """
    from fastapi.testclient import TestClient

    # backend.app.main constructs a module-level app on first import. Point
    # that import at the scratch database too; our TestClient gets an explicit
    # scratch URL regardless of Python's module cache.
    previous_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    get_settings.cache_clear()
    try:
        from backend.app.main import create_app
    finally:
        if previous_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_database_url
        get_settings.cache_clear()

    app = create_app(
        database_url=database_url,
        settings=settings,
        embedding_provider=DeterministicEmbeddingProvider(),
        reflection_provider=FakeReflectionProvider(),
        planning_provider=planning_provider,
    )
    durations: list[float] = []
    try:
        with TestClient(app) as client:
            for index in range(ticks):
                world = client.get("/api/world").json()["data"]["world"]
                version = world["world_version"]
                if isinstance(planning_provider, MeteredPlanningProvider):
                    planning_provider.begin_tick(world["clock_tick"] + 1)
                started = time.monotonic()
                response = client.post(
                    "/api/world/tick", json={"expected_world_version": version}
                )
                durations.append(time.monotonic() - started)
                if response.status_code != 200:
                    raise RuntimeError(
                        f"tick {index + 1} 返回 {response.status_code}: {response.text[:200]}"
                    )
                print(f"  tick {index + 1:>3}/{ticks}  {durations[-1]:5.1f}s", flush=True)
    finally:
        # create_app 不回传 engine 句柄，只留 sessionmaker。取回它的 bind 释放
        # 连接池，否则临时库文件在 Windows 上仍被占用、无法删除。
        bind = app.state.session_factory.kw.get("bind")
        if bind is not None:
            bind.dispose()
    return durations


def collect(database_url: str, samples: tuple[CallSample, ...]) -> dict:
    engine, session_factory = create_engine_and_session(database_url)
    try:
        with session_factory() as session:
            traces = list(session.scalars(
                select(AgentTraceEntry).where(
                    AgentTraceEntry.stage.in_(("planning", "proposal", "rule_rejection"))
                )
            ))
            plans = list(session.scalars(select(AgentPlan)))
            actions = list(session.scalars(select(WorldAction)))
            runs = list(session.scalars(select(AgentRun)))
    finally:
        engine.dispose()

    tick_of_run = {run.id: run.resulting_clock_tick for run in runs}
    sampled = {(sample.tick, sample.npc_id): sample for sample in samples}

    planned: dict[tuple[str, str], str] = {}
    executed: dict[tuple[str, str], str] = {}
    # 落盘的失败分类，`<stage>:<code>`。直接读它，不再从 source 反推 —— 反推能算对
    # 总数，却答不出「哪条规则拒了什么动作」。
    persisted_reason: dict[tuple[str, str], str] = {}
    for entry in traces:
        actor = entry.actor_id or entry.data_json.get("npc_id")
        if actor is None:
            continue
        if entry.stage == "rule_rejection":
            persisted_reason[(entry.run_id, actor)] = (
                f"rule:{entry.data_json.get('failure_code', 'unspecified')}"
            )
            continue
        if entry.stage == "planning" and entry.data_json.get("failure_stage") == "provider":
            persisted_reason[(entry.run_id, actor)] = (
                f"provider:{entry.data_json.get('failure_code') or 'unknown'}"
            )
        target = planned if entry.stage == "planning" else executed
        target[(entry.run_id, actor)] = entry.data_json.get("source", "unknown")

    # 动作合法率：模型产出的提案里，没有被引擎替换掉的比例。
    # `llm` 与 `existing_plan` 都是模型写的步骤，被拒同样说明它没理解工具约束。
    authored = [key for key, source in planned.items() if source in MODEL_AUTHORED]
    survived = sum(executed.get(key) == planned[key] for key in authored)

    fallback = sum(source == "fallback" for source in executed.values())
    fallback_reasons = Counter()
    for (run_id, actor), source in executed.items():
        if source != "fallback":
            continue
        reason = persisted_reason.get((run_id, actor))
        if reason is not None:
            fallback_reasons[reason] += 1
            continue
        # trace 里没有分类：说明 planner 根本没为这个 NPC 产出结果（例如检索或
        # 计划写入抛异常，`decide_many` 会跳过它）。如实记为「未落盘」，不拿
        # 进程内计量去补 —— 补出来的数字无法由 trace 复核。
        fallback_reasons["unattributed"] += 1
    completed = sum(plan.status == "completed" for plan in plans)
    distribution = Counter(action.action_type for action in actions)

    return {
        "call_success": sum(sample.decision_ok for sample in samples),
        "provider_calls": len(samples),
        "survived": survived, "authored": len(authored),
        "fallback": fallback, "proposals": len(executed),
        "untraced_deterministic": sum(
            source == "deterministic" and key not in planned
            for key, source in executed.items()
        ),
        "reuse": sum(source == "existing_plan" for source in executed.values()),
        "fallback_reasons": fallback_reasons,
        "proposal_samples": [
            {"tick": tick_of_run[run_id], "npc_id": actor,
             "planning_source": planned.get((run_id, actor)), "executed_source": source}
            for (run_id, actor), source in sorted(executed.items())
        ],
        "completed": completed, "plans": len(plans),
        "plan_statuses": [plan.status for plan in plans],
        "distribution": distribution,
        "action_types": [action.action_type for action in actions],
        "entropy": shannon_entropy(distribution.values()),
        "call_durations_ms": [sample.duration_ms for sample in samples],
        "tokens": [sample.tokens_used for sample in samples if sample.tokens_used is not None],
    }


def build_evidence(stats: dict, durations: list[float],
                   samples: tuple[CallSample, ...]) -> dict:
    """Machine-readable, content-free inputs for auditing every report row."""
    return {
        "schema_version": 1,
        "percentile_method": "nearest_rank",
        "counts": {
            key: stats[key] for key in (
                "call_success", "provider_calls", "survived", "authored",
                "fallback", "proposals", "reuse", "completed", "plans",
                "untraced_deterministic",
            )
        },
        "fallback_reasons": dict(stats["fallback_reasons"]),
        "proposal_samples": stats["proposal_samples"],
        "plan_statuses": stats["plan_statuses"],
        "action_types": stats["action_types"],
        "tick_durations_seconds": durations,
        "call_samples": [asdict(sample) for sample in samples],
    }


def render(stats: dict, *, ticks: int, provider_label: str, model: str,
           durations: list[float]) -> str:
    entropy, max_entropy = stats["entropy"], math.log2(len(DEFAULT_ACTION_REGISTRY.action_types))
    collapse = " ⚠️ 存在行为坍缩风险" if 0 < entropy < BEHAVIOUR_COLLAPSE_THRESHOLD else ""
    spread = "、".join(
        f"{action} {count}" for action, count in sorted(stats["distribution"].most_common())
    ) or "无"
    latencies, tokens = stats["call_durations_ms"], stats["tokens"]

    def duration_pair(values: list[float], scale: float, unit: str) -> str:
        p50, p95 = percentile(values, .50), percentile(values, .95)
        if p50 is None or p95 is None:
            return "—（无样本）"
        if scale == 1000 and max(values) < 1000:
            return f"P50 {p50:.2f}ms / P95 {p95:.2f}ms（n={len(values)}）"
        return f"P50 {p50 / scale:.3f}{unit} / P95 {p95 / scale:.3f}{unit}（n={len(values)}）"

    lines: list[str] = [
        "# Stage 3m Agent Evaluation",
        "",
        f"- 生成时间：{datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')} UTC",
        f"- Provider：`{provider_label}`　Model：`{model}`",
        f"- Tick 数：{ticks}　动作空间：{len(DEFAULT_ACTION_REGISTRY.action_types)} 个动词",
        "",
        "| 指标 | 值 | 含义 |",
        "| --- | --- | --- |",
        f"| 动作合法率 | {_percent(stats['survived'], stats['authored'])} "
        "| 未被规则替换的计划步骤 / 所有计划步骤提案；planning + proposal trace |",
        f"| 可用决策率 | {_percent(stats['call_success'], stats['provider_calls'])} "
        "| 返回可用 AgentDecision / 实际 Provider 调用；调用计量，失败不等于 Schema 错误 |",
        f"| 兜底率 | {_percent(stats['fallback'], stats['proposals'])} "
        "| source=fallback / 全部 NPC 提案；proposal trace |",
        f"| 计划完成率（状态） | {_percent(stats['completed'], stats['plans'])} "
        "| status=completed / 创建的计划行；含窗口截尾与过龄结束，非语义目标达成 |",
        f"| 行为熵 | {entropy:.3f} / {max_entropy:.3f}{collapse} "
        "| actions.action_type 分布的香农熵；n=动作行数，描述多样性 |",
        f"| 计划复用率 | {_percent(stats['reuse'], stats['proposals'])} "
        "| source=existing_plan / 全部 NPC 提案；proposal trace |",
        (
            f"| 模型调用 / NPC-tick | {stats['provider_calls']}/{stats['proposals']} = "
            f"{stats['provider_calls'] / stats['proposals']:.3f} "
            "| 本次 Provider 调用计量 / 全部 NPC 提案 |"
            if stats["proposals"] else "| 模型调用 / NPC-tick | —（样本为 0） | — |"
        ),
        f"| tick 耗时 | {duration_pair(durations, 1, 's')} "
        "| POST /api/world/tick 墙钟耗时，含规划、持久化和认知投影 |",
        f"| 模型调用耗时 | {duration_pair(latencies, 1000, 's')} "
        "| Provider.plan 墙钟耗时，成功与失败均计入 |",
    ]
    lines.append(
        f"| 已上报 token | {sum(tokens)}（覆盖 {len(tokens)}/{stats['provider_calls']} 次调用） "
        "| usage.total_tokens 求和；未上报调用的消耗未知 |"
        if tokens else f"| 已上报 token | —（覆盖 0/{stats['provider_calls']} 次调用） "
        "| Provider 未上报，消耗未知 |"
    )
    for reason, count in sorted(stats["fallback_reasons"].items()):
        lines.append(
            f"| 兜底原因：{describe_failure(reason)} | "
            f"{_percent(count, stats['fallback'])} | 本项次数 / source=fallback 提案数；落盘 trace |"
        )
    if stats["untraced_deterministic"]:
        lines.append(
            f"| 未记录规划的确定性提案 | {stats['untraced_deterministic']} "
            "| proposal trace 有 deterministic、无 planning trace；不并入 source=fallback 分子 |"
        )
    lines += [
        "",
        f"动作分布：{spread}",
        "",
        "> 指标口径：`llm` 与 `existing_plan` 都算规划 Provider 产出的提案；`existing_plan`"
        " 不调用模型。P50/P95 用 nearest-rank（向上取整名次）。Embedding 与 Reflection "
        "固定使用确定性替身；Fake 结果只验证链路，不代表真实模型可用率。",
        "> 失败归因：兜底原因直接读落盘 trace，格式 `<stage>:<code>`。`provider:*` "
        "来自 adapter 按异常类型分的四类（timeout / http_status / transport / "
        "parse_error），`rule:*` 是 `ActionRegistry` 与 conflict_resolver 的拒绝码，"
        "由 `rule_rejection` trace 记录被替换掉的原始提案。拿不到分类时记 "
        "`provider:unknown` 或 `unattributed`，不按异常长相臆造具体原因。",
        "> 使用 `--out` 时，同名 `.evidence.json` 保存去内容化的逐 tick、逐调用与逐提案"
        "样本，以及分子分母；不会保存 Prompt、模型响应或凭据。",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 3m Agent Evaluation")
    parser.add_argument("--ticks", type=int, default=20)
    parser.add_argument("--provider", choices=("fake", "live"), default="fake")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    if args.ticks < 1:
        print("--ticks 必须 >= 1", file=sys.stderr)
        return 2

    if args.provider == "live":
        # Live is the only mode allowed to read the operator's explicit
        # planning credentials. It is never used by the Fake test path.
        settings = Settings()
        provider = build_planning_provider(settings)
        if not isinstance(provider, OpenAICompatiblePlanningProvider):
            print(
                "--provider live 需要完整的 PLANNING_PROVIDER_BASE_URL / _API_KEY / _MODEL；"
                "当前配置只能装配出替身，未执行评估。",
                file=sys.stderr,
            )
            return 1
    else:
        # Do this before importing backend.app.main: that module constructs an
        # application at import time. Fake evaluation must not read .env or
        # accidentally assemble any paid provider from inherited environment.
        _isolate_provider_environment()
        provider = FakePlanningProvider()

    # The imported default app and our TestClient both use safe settings.
    # The already-built Live planning provider retains its own credentials.
    _isolate_provider_environment()
    meter = MeteredPlanningProvider(provider)
    label, model = meter.provider_name, meter.model_name

    workspace = Path(tempfile.mkdtemp(prefix="aleria-eval-"))
    database_url = f"sqlite:///{(workspace / 'eval.db').as_posix()}"
    try:
        print(f"隔离数据库：{workspace / 'eval.db'}")
        seed_database(database_url, REPO_ROOT / "data")
        safe_settings = Settings(
            _env_file=None, database_url=database_url, chat_provider="mock",
            embedding_provider="fake", reflection_provider="fake",
            planning_provider_base_url="", planning_provider_api_key="",
            planning_provider_model="",
        )
        durations = run_ticks(database_url, args.ticks, meter, safe_settings)
        stats = collect(database_url, meter.samples)
        report = render(
            stats, ticks=args.ticks,
            provider_label=label, model=model, durations=durations,
        )
        evidence = build_evidence(stats, durations, meter.samples)
    finally:
        remove_workspace(workspace)

    print()
    print(report)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report + "\n", encoding="utf-8")
        evidence_path = args.out.with_suffix(".evidence.json")
        evidence_path.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"\n已写入 {args.out}")
        print(f"已写入 {evidence_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
