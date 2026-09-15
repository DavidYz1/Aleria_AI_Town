"""Stage 3m Agent Loop：Context 组装 + Plan 生命周期状态机。

spec §6 的五条规则在 `AgentPlanner.decide` 内实现，spec §7 的八段式 Context 在
`build_context` 内实现。本模块**不做任何世界写入** —— 它只产出 `ActionProposal`，
校验、冲突处理与执行仍然归 orchestrator。
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import logging
import time

from backend.app.agents.action_registry import ActionRegistry
from backend.app.agents.contracts import ActionProposal, ProposalSource
from backend.app.agents.memory_retrieval import MemoryType, RetrievalRequest, RetrievalScope
from backend.app.agents.planning_contracts import AgentDecision
from backend.app.llm.planning_provider import PlanningRequest
from backend.app.world.decision import decide_action
from backend.app.world.types import NpcSnapshot, WorldSnapshot


logger = logging.getLogger(__name__)

# 上限而非目标值：演示世界只有三个 NPC，但世界变大时不应为每个 NPC 各开一条连接。
MAX_PLANNING_WORKERS = 8


@dataclass(frozen=True)
class _PendingDecision:
    """`_prepare` 产出、等待模型回答的中间态。只带纯数据，不带 Session。"""

    request: PlanningRequest


@dataclass(frozen=True)
class _ProviderAnswer:
    decision: AgentDecision | None
    latency_ms: int
    tokens_used: int | None


@dataclass(frozen=True)
class LastOutcome:
    action_type: str
    accepted: bool
    code: str


@dataclass(frozen=True)
class PlanningOutcome:
    proposal: ActionProposal
    source: ProposalSource
    plan: object | None
    decision: AgentDecision | None
    latency_ms: int | None
    tokens_used: int | None


class AgentPlanner:
    """`current_step_index` 的语义：**本 tick 正在执行的步骤序号**。

    因此复用分支先 `advance_step` 再读取 —— 创建计划的那一 tick 已经执行过
    `steps[0]`，下一 tick 必须落到 `steps[1]`。调用方（Service）不得再次
    `advance_step`，否则会跳步。
    """

    def __init__(self, repository, retriever, provider, registry: ActionRegistry, *, max_plan_age_ticks: int = 8):
        self._repository = repository
        self._retriever = retriever
        self._provider = provider
        self._registry = registry
        self._max_plan_age_ticks = max_plan_age_ticks

    def decide(self, world: WorldSnapshot, actor: NpcSnapshot, *, last_outcome: LastOutcome | None) -> PlanningOutcome:
        """单个 NPC 的串行路径：三相依次执行，行为与拆分前逐字段相同。"""
        prepared = self._prepare(world, actor, last_outcome)
        if isinstance(prepared, PlanningOutcome):
            return prepared
        return self._settle_answer(world, actor, self._ask(prepared))

    def decide_many(self, world: WorldSnapshot, actors, *,
                    last_outcome: LastOutcome | None) -> dict[str, PlanningOutcome]:
        """多个 NPC：**只有纯网络的那一相并发**，两侧的数据库操作仍然串行。

        这条边界是刻意的。`PlanRepository` 与 `persist_run` 共用同一个 tick Session，
        SQLAlchemy 的 Session 不是线程安全的；`_retrieve` 又要求所在 Session 没有
        进行中的事务。把它们放进线程池会制造难以复现的竞争。
        `provider.plan()` 不持有任何 Session，是唯一可以安全并发的部分 ——
        它也恰好是耗时的全部（实测单次 12–19 秒，另外两相合计约 30 毫秒）。

        单个 NPC 的任何失败只影响它自己：缺席的 NPC 由 orchestrator 走
        确定性 `decide_action`（spec §13 唯一不变量）。
        """
        prepared: list[tuple[NpcSnapshot, PlanningOutcome | _PendingDecision | None]] = []
        for actor in actors:
            try:
                prepared.append((actor, self._prepare(world, actor, last_outcome)))
            except Exception:
                logger.warning("Planning preparation failed npc_id=%s", actor.id)
                prepared.append((actor, None))

        pending = [(actor, item) for actor, item in prepared if isinstance(item, _PendingDecision)]
        answers = self._ask_all(pending)

        outcomes: dict[str, PlanningOutcome] = {}
        for actor, item in prepared:
            if isinstance(item, PlanningOutcome):
                outcomes[actor.id] = item
            elif item is not None:
                try:
                    outcomes[actor.id] = self._settle_answer(world, actor, answers[actor.id])
                except Exception:
                    logger.warning("Planning persistence failed npc_id=%s", actor.id)
        return outcomes

    def _prepare(self, world: WorldSnapshot, actor: NpcSnapshot,
                 last_outcome: LastOutcome | None) -> "PlanningOutcome | _PendingDecision":
        """第一相：全部数据库读写。要么直接定案（复用计划），要么产出待问的请求。"""
        plan = self._repository.get_active(world.id, actor.id)

        # 规则 5：过龄强制放弃
        if plan is not None and world.clock_tick - plan.created_clock_tick > self._max_plan_age_ticks:
            self._repository.abandon(plan, clock_tick=world.clock_tick)
            plan = None

        # 规则 2：复用计划，不调模型
        if plan is not None:
            plan = self._repository.advance_step(plan, clock_tick=world.clock_tick)
            if plan.status != "completed":
                # 规则 4 的另一侧：步骤未用尽才复用，用尽则落到下面重新规划
                return PlanningOutcome(
                    proposal=self._to_proposal(
                        actor, plan.steps_json[plan.current_step_index], ProposalSource.EXISTING_PLAN
                    ),
                    source=ProposalSource.EXISTING_PLAN,
                    plan=plan, decision=None, latency_ms=None, tokens_used=None,
                )

        # 规则 1：调模型生成新计划
        memories = self._retrieve(world, actor)
        return _PendingDecision(request=PlanningRequest(
            npc_id=actor.id,
            context_text=self.build_context(world, actor, None, memories, last_outcome),
            tool_manifest=self._registry.to_tool_manifest(),
        ))

    def _ask(self, pending: "_PendingDecision") -> "_ProviderAnswer":
        """第二相：纯网络，不碰任何 Session。失败在这里被吞成 `decision=None`。

        token 必须在**发起调用的同一线程里**读出：provider 把它记在 thread-local
        上，跨线程读会拿到别人的数字（`planning_provider.py` 的同名属性）。
        """
        started = time.monotonic()
        try:
            decision = self._provider.plan(pending.request)
        except Exception:
            # spec §13 唯一不变量：任何失败都必须产出可执行提案。
            # 捕获宽泛 Exception 是刻意的，不是遗漏 —— PlanningProviderError 之外的
            # 任何意外（网络栈、序列化、第三方库）都不得让世界停摆。
            return _ProviderAnswer(None, int((time.monotonic() - started) * 1000), None)
        return _ProviderAnswer(
            decision, int((time.monotonic() - started) * 1000),
            getattr(self._provider, "last_tokens_used", None),
        )

    def _ask_all(self, pending) -> dict[str, "_ProviderAnswer"]:
        if not pending:
            return {}
        if len(pending) == 1:
            actor, item = pending[0]
            return {actor.id: self._ask(item)}
        with ThreadPoolExecutor(max_workers=min(len(pending), MAX_PLANNING_WORKERS)) as pool:
            futures = {actor.id: pool.submit(self._ask, item) for actor, item in pending}
            return {npc_id: future.result() for npc_id, future in futures.items()}

    def _settle_answer(self, world: WorldSnapshot, actor: NpcSnapshot,
                       answer: "_ProviderAnswer") -> PlanningOutcome:
        """第三相：回到调用线程串行写库。"""
        if answer.decision is None:
            return PlanningOutcome(
                proposal=decide_action(actor, world), source=ProposalSource.FALLBACK,
                plan=None, decision=None, latency_ms=None, tokens_used=None,
            )
        created = self._repository.create_from_decision(
            world.id, actor.id, answer.decision,
            clock_tick=world.clock_tick, run_id=None,
            provider=getattr(self._provider, "provider_name", "unknown"),
            model=getattr(self._provider, "model_name", "unknown"),
            latency_ms=answer.latency_ms,
            tokens_used=answer.tokens_used,
        )
        return PlanningOutcome(
            proposal=self._to_proposal(actor, created.steps_json[0], ProposalSource.LLM),
            source=ProposalSource.LLM, plan=created, decision=answer.decision,
            latency_ms=answer.latency_ms, tokens_used=created.tokens_used,
        )

    def settle(self, world: WorldSnapshot, outcome: "PlanningOutcome", final_proposal: ActionProposal) -> None:
        """世界推进后回填计划状态：spec §6 规则 3 —— step 被引擎拒绝则放弃该计划。

        `advance_step` 由 `decide` 在消费步骤时完成，调用方不得重复推进。
        """
        if outcome.plan is not None and final_proposal.source is ProposalSource.FALLBACK:
            self._repository.abandon(outcome.plan, clock_tick=world.clock_tick)

    def build_context(self, world, actor, active_plan, memories, last_outcome) -> str:
        """spec §7 八段式。每段以 [SectionName] 开头，便于模型定位与人工排错。"""
        others = [n for n in world.npcs if n.location_id == actor.location_id and n.id != actor.id]
        return "\n".join(
            [
                f"[Identity] {actor.name}（{actor.role}），性格：{'、'.join(actor.personality)}",
                f"[Needs] 体力 {actor.energy} / 心情 {actor.mood} / 社交 {actor.social}（低于 40 视为亟需处理）",
                f"[World] 第 {world.day} 天 {world.time}，当前位于 {actor.location_id}；"
                f"同地点：{'、'.join(n.id for n in others) or '无'}；"
                f"可达地点：{'、'.join(loc.id for loc in world.locations)}",
                "[Episodic] " + ("；".join(m.content for m in memories) if memories else "暂无相关经历"),
                "[Semantic] 暂无已确立的信念",
                "[Procedural] " + (
                    f"当前计划「{active_plan.goal}」进行到第 {active_plan.current_step_index + 1} 步"
                    if active_plan is not None else "当前没有进行中的计划"
                ),
                # 只列动作名：完整描述已经随 `tools` 数组发出去了（实测占请求体 75%），
                # 在这里再抄一遍等于让模型为同一份内容付两次 prompt token。
                # spec §7 的八段式要求这一段存在，所以保留段落、压缩内容。
                "[Tools] 可用工具："
                + "、".join(t["name"] for t in self._registry.to_tool_manifest())
                + "（参数与约束见工具定义）",
                "[LastOutcome] " + (
                    f"上一步 {last_outcome.action_type} "
                    f"{'成功' if last_outcome.accepted else '被拒绝'}（{last_outcome.code}）"
                    if last_outcome is not None else "这是本次决策的起点，没有上一步结果"
                ),
            ]
        )

    def _retrieve(self, world: WorldSnapshot, actor: NpcSnapshot):
        try:
            return self._retriever.retrieve(
                RetrievalRequest(
                    world_id=world.id, owner_npc_id=actor.id,
                    current_world_version=world.world_version,
                    current_clock_tick=world.clock_tick,
                    query_text=f"{actor.role} 当前处境与近期经历",
                    scope=RetrievalScope.INTERNAL_REFLECTION,
                    allowed_memory_types=frozenset(MemoryType),
                    limit=6, char_budget=1200,
                    # 本调用发生在 world tick 的事务内、且走第二个连接：写 telemetry
                    # 拿不到锁，只会等满 busy timeout 再被静默吞掉。
                    record_access=False,
                )
            ).memories
        except Exception:
            return ()

    def _to_proposal(self, actor: NpcSnapshot, step: dict, source: ProposalSource) -> ActionProposal:
        return ActionProposal(
            actor_id=actor.id, action_type=step["action_type"],
            target_kind=step.get("target_kind"), target_id=step.get("target_id"),
            reason_code="agent_plan", source=source,
        )
