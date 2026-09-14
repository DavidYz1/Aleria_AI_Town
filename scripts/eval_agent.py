"""Stage 3m Agent Evaluation：离线跑 N tick，输出 markdown 指标表。

隔离原则：每次运行都新建一个临时 SQLite 数据库并迁移到 head，
**绝不打开 `backend/data/aleria.db`**。

指标全部从**已落盘的数据**计算，不复算业务逻辑：
- `agent_trace_entries` 的 `planning` 段记录 planner 产出的来源；
- 同一 run 的 `proposal` 段记录**经 `_with_fallback` 替换之后**真正执行的来源。
两者逐 (run, actor) 配对即可区分「模型没返回可用结果」与「模型返回了但动作被引擎拒绝」，
不需要在脚本里重新实现一遍校验。

用法：
    python scripts/eval_agent.py --ticks 20 --provider fake
    python scripts/eval_agent.py --ticks 20 --provider live --out docs/eval/report.md
"""
import argparse
from collections import Counter
from datetime import UTC, datetime
import json
import math
from pathlib import Path
import shutil
import sys
import tempfile
import time

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import select

from backend.app.core.config import Settings
from backend.app.database.connection import create_engine_and_session
from backend.app.database.models import AgentPlan, AgentTraceEntry, WorldAction
from backend.app.llm.embedding_provider import DeterministicEmbeddingProvider
from backend.app.llm.planning_provider import (
    FakePlanningProvider,
    OpenAICompatiblePlanningProvider,
    build_planning_provider,
)
from backend.app.llm.reflection_provider import FakeReflectionProvider
from backend.app.world.action_rules import DEFAULT_ACTION_REGISTRY
from scripts.seed_world import seed_database


MODEL_AUTHORED = ("llm", "existing_plan")
BEHAVIOUR_COLLAPSE_THRESHOLD = 1.0


def shannon_entropy(counts) -> float:
    total = sum(counts)
    if total == 0:
        return 0.0
    return -sum((n / total) * math.log2(n / total) for n in counts if n)


def _percent(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "—（样本为 0）"
    return f"{numerator / denominator:.1%}（{numerator}/{denominator}）"


def run_ticks(database_url: str, ticks: int, planning_provider) -> list[float]:
    """真实跑 `POST /api/world/tick`，走和游戏完全相同的路由与持久化路径。

    Embedding 与 Reflection 一律注入替身：本脚本评估的是规划回路，
    让 live reflection 一起跑只会在每 tick 上叠加十几秒与额外开销，
    并不改变任何一项指标。
    """
    from fastapi.testclient import TestClient

    from backend.app.main import create_app

    app = create_app(
        database_url=database_url,
        embedding_provider=DeterministicEmbeddingProvider(),
        reflection_provider=FakeReflectionProvider(),
        planning_provider=planning_provider,
    )
    durations: list[float] = []
    with TestClient(app) as client:
        for index in range(ticks):
            version = client.get("/api/world").json()["data"]["world"]["world_version"]
            started = time.monotonic()
            response = client.post("/api/world/tick", json={"expected_world_version": version})
            durations.append(time.monotonic() - started)
            if response.status_code != 200:
                raise RuntimeError(
                    f"tick {index + 1} 返回 {response.status_code}: {response.text[:200]}"
                )
            print(f"  tick {index + 1:>3}/{ticks}  {durations[-1]:5.1f}s", flush=True)
    return durations


def collect(database_url: str) -> dict:
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        traces = list(session.scalars(
            select(AgentTraceEntry).where(AgentTraceEntry.stage.in_(("planning", "proposal")))
        ))
        plans = list(session.scalars(select(AgentPlan)))
        actions = list(session.scalars(select(WorldAction)))

    planned: dict[tuple[str, str], str] = {}
    executed: dict[tuple[str, str], str] = {}
    for entry in traces:
        actor = entry.actor_id or entry.data_json.get("npc_id")
        if actor is None:
            continue
        target = planned if entry.stage == "planning" else executed
        target[(entry.run_id, actor)] = entry.data_json.get("source", "unknown")

    # Schema 有效率：planner 调了模型的那些 tick 里，返回可用 AgentDecision 的比例。
    # `existing_plan` 没有调模型，不计入分母。
    provider_calls = [source for source in planned.values() if source in ("llm", "fallback")]
    schema_ok = sum(source == "llm" for source in provider_calls)

    # 动作合法率：模型产出的提案里，没有被引擎替换掉的比例。
    # `llm` 与 `existing_plan` 都是模型写的步骤，被拒同样说明它没理解工具约束。
    authored = [key for key, source in planned.items() if source in MODEL_AUTHORED]
    survived = sum(executed.get(key) == planned[key] for key in authored)

    fallback = sum(source == "fallback" for source in executed.values())
    completed = sum(plan.status == "completed" for plan in plans)
    latencies = [plan.latency_ms for plan in plans if plan.latency_ms is not None]
    tokens = [plan.tokens_used for plan in plans if plan.tokens_used is not None]
    distribution = Counter(action.action_type for action in actions)

    return {
        "schema_ok": schema_ok, "provider_calls": len(provider_calls),
        "survived": survived, "authored": len(authored),
        "fallback": fallback, "proposals": len(executed),
        "completed": completed, "plans": len(plans),
        "distribution": distribution,
        "entropy": shannon_entropy(distribution.values()),
        "latencies": latencies, "tokens": tokens,
    }


def render(stats: dict, *, ticks: int, provider_label: str, model: str,
           durations: list[float]) -> str:
    entropy, max_entropy = stats["entropy"], math.log2(len(DEFAULT_ACTION_REGISTRY.action_types))
    collapse = " ⚠️ 存在行为坍缩风险" if 0 < entropy < BEHAVIOUR_COLLAPSE_THRESHOLD else ""
    spread = "、".join(
        f"{action} {count}" for action, count in sorted(stats["distribution"].most_common())
    ) or "无"
    latencies, tokens = stats["latencies"], stats["tokens"]

    # None = 这一行不输出。用 None 而不是空串，否则下面的过滤会把刻意留的
    # 空行一并删掉，markdown 表格前没有空行就不会被渲染成表格。
    lines: list[str | None] = [
        "# Stage 3m Agent Evaluation",
        "",
        f"- 生成时间：{datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')} UTC",
        f"- Provider：`{provider_label}`　Model：`{model}`",
        f"- Tick 数：{ticks}　动作空间：{len(DEFAULT_ACTION_REGISTRY.action_types)} 个动词",
        "",
        "| 指标 | 值 | 含义 |",
        "| --- | --- | --- |",
        f"| 动作合法率 | {_percent(stats['survived'], stats['authored'])} "
        "| 模型产出的提案中未被引擎替换的比例 —— 它是否理解工具约束 |",
        f"| Schema 有效率 | {_percent(stats['schema_ok'], stats['provider_calls'])} "
        "| 调用模型的 tick 中一次返回合法 `AgentDecision` 的比例 |",
        f"| 兜底率 | {_percent(stats['fallback'], stats['proposals'])} "
        "| 实际由确定性策略执行的提案占比 —— 韧性的真实触发频率 |",
        f"| 目标达成率 | {_percent(stats['completed'], stats['plans'])} "
        "| `completed` 计划占全部计划的比例 —— 规划质量 |",
        f"| 行为熵 | {entropy:.3f} / {max_entropy:.3f}{collapse} "
        "| 动作类型分布的香农熵，防「NPC 一直吃饭」的行为坍缩 |",
        f"| 平均规划延迟 | {sum(latencies) / len(latencies):.0f} ms "
        if latencies else "| 平均规划延迟 | —（无计划行） ",
    ]
    lines[-1] += "| 单次模型调用的平均耗时 |"
    lines.append(
        f"| 累计 token | {sum(tokens)}（{len(tokens)} 次计费调用） | 本次评估的总消耗 |"
        if tokens else "| 累计 token | —（provider 未上报） | 本次评估的总消耗 |"
    )
    lines += [
        "",
        f"动作分布：{spread}",
        "",
        (
            f"平均 tick 耗时：{sum(durations) / len(durations):.1f}s"
            f"（最慢 {max(durations):.1f}s）"
        ) if durations else None,
        "",
        "> 指标口径：`llm` 与 `existing_plan` 都算模型产出的提案；`existing_plan`"
        " 不调用模型，因此不计入 Schema 有效率的分母。Embedding 与 Reflection 在评估中"
        "固定使用确定性替身，本表只反映规划回路。",
    ]
    return "\n".join(line for line in lines if line is not None)


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 3m Agent Evaluation")
    parser.add_argument("--ticks", type=int, default=20)
    parser.add_argument("--provider", choices=("fake", "live"), default="fake")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    if args.ticks < 1:
        print("--ticks 必须 >= 1", file=sys.stderr)
        return 2

    settings = Settings()
    if args.provider == "live":
        provider = build_planning_provider(settings)
        if not isinstance(provider, OpenAICompatiblePlanningProvider):
            print(
                "--provider live 需要完整的 PLANNING_PROVIDER_BASE_URL / _API_KEY / _MODEL；"
                "当前配置只能装配出替身，未执行评估。",
                file=sys.stderr,
            )
            return 1
        label, model = provider.provider_name, provider.model_name
    else:
        provider = FakePlanningProvider()
        label, model = provider.provider_name, provider.model_name

    workspace = Path(tempfile.mkdtemp(prefix="aleria-eval-"))
    database_url = f"sqlite:///{(workspace / 'eval.db').as_posix()}"
    try:
        print(f"隔离数据库：{workspace / 'eval.db'}")
        seed_database(database_url, REPO_ROOT / "data")
        durations = run_ticks(database_url, args.ticks, provider)
        report = render(
            collect(database_url), ticks=args.ticks,
            provider_label=label, model=model, durations=durations,
        )
    finally:
        shutil.rmtree(workspace, ignore_errors=True)

    print()
    print(report)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report + "\n", encoding="utf-8")
        print(f"\n已写入 {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
