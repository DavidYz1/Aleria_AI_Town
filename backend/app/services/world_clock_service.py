from dataclasses import replace
import logging
from uuid import uuid4

from backend.app.agents.contracts import (
    AgentRuntimeResult,
    ProposalSource,
    RuntimeMode,
    TraceDraft,
)
from backend.app.agents.orchestrator import run_advance
from backend.app.agents.planner import AgentPlanner, PlanningOutcome
from backend.app.schemas.agent_run import AgentRunSummary
from backend.app.database.action_compat import to_public_action_type
from backend.app.database.world_clock_repository import (
    WorldTickConflictError,
    WorldTickRepository,
)
from backend.app.schemas.world import (
    LocationInfo,
    NpcInfo,
    NpcStatus,
    WorldData,
    WorldInfo,
)
from backend.app.schemas.world_clock import (
    WorldActionInfo,
    WorldEventInfo,
    WorldTickData,
)
from backend.app.world.types import WorldSnapshot
from backend.app.services.cognition_projection import CognitionProjectionError, CognitionProjectionService


logger = logging.getLogger(__name__)


def snapshot_to_world_data(snapshot: WorldSnapshot) -> WorldData:
    return WorldData(
        world=WorldInfo(
            id=snapshot.id,
            name=snapshot.name,
            day=snapshot.day,
            time=snapshot.time,
            world_version=snapshot.world_version,
            clock_tick=snapshot.clock_tick,
            event_sequence=snapshot.event_sequence,
        ),
        locations=[
            LocationInfo(
                id=location.id,
                name=location.name,
                description=location.description,
            )
            for location in snapshot.locations
        ],
        npcs=[
            NpcInfo(
                id=npc.id,
                name=npc.name,
                role=npc.role,
                personality=list(npc.personality),
                location_id=npc.location_id,
                current_action=npc.current_action,
                status=NpcStatus(
                    energy=npc.energy,
                    mood=npc.mood,
                    social=npc.social,
                ),
            )
            for npc in snapshot.npcs
        ],
    )


def _planning_trace(npc_id: str, outcome: PlanningOutcome) -> TraceDraft:
    plan = outcome.plan
    return TraceDraft(
        sequence=0,  # 插入时统一重排
        stage="planning",
        actor_id=npc_id,
        summary="Planning decision recorded",
        data={
            "npc_id": npc_id,
            "source": outcome.source.value,
            "goal": plan.goal if plan is not None else "确定性兜底，本 tick 未生成计划",
            "thought": plan.thought if plan is not None else "规划不可用，回退到确定性策略",
            "provider": plan.provider if plan is not None else "deterministic",
            "model": plan.model if plan is not None else "rule-based",
            "latency_ms": outcome.latency_ms,
            "tokens_used": outcome.tokens_used,
        },
    )


def _with_planning_traces(
    result: AgentRuntimeResult,
    planning: list[TraceDraft],
) -> AgentRuntimeResult:
    """把 planning trace 插在 run_started 之后并重排 sequence。

    持久化层要求 sequence 连续且 planning 段紧随 run_started。
    """
    if not planning:
        return result
    ordered = [result.traces[0], *planning, *result.traces[1:]]
    return replace(
        result,
        traces=tuple(
            replace(trace, sequence=sequence)
            for sequence, trace in enumerate(ordered, 1)
        ),
    )


class WorldTickService:
    def __init__(
        self,
        repository: WorldTickRepository,
        cognition: CognitionProjectionService | None = None,
        planner: AgentPlanner | None = None,
    ) -> None:
        self._repository = repository
        self._cognition = cognition
        self._planner = planner

    def advance(
        self,
        expected_world_version: int,
        runtime_mode: RuntimeMode = RuntimeMode.AUTO,
    ) -> WorldTickData:
        snapshot = self._repository.get_snapshot()
        if snapshot.world_version != expected_world_version:
            raise WorldTickConflictError("world version conflict; refresh and retry")

        outcomes = self._plan(snapshot, runtime_mode)
        override = {
            npc_id: (
                replace(outcome.proposal, source=ProposalSource.FALLBACK)
                if outcome.source is ProposalSource.FALLBACK
                else outcome.proposal
            )
            for npc_id, outcome in outcomes.items()
        }
        runtime_result = _with_planning_traces(
            run_advance(snapshot, proposal_override=override or None),
            [_planning_trace(npc_id, outcome) for npc_id, outcome in outcomes.items()],
        )
        # 计划回填必须发生在 persist_run 之前，两者共用同一 Session，
        # 从而与 run / action / event 在同一事务里提交或回滚。
        final = {proposal.actor_id: proposal for proposal in runtime_result.proposals}
        for npc_id, outcome in outcomes.items():
            self._planner.settle(snapshot, outcome, final[npc_id])

        persisted = self._repository.persist_run(
            str(uuid4()), expected_world_version, runtime_result,
            correlation_id=str(uuid4()),
        )
        result = WorldTickData(
            run=AgentRunSummary.model_validate(persisted.run),
            world=snapshot_to_world_data(persisted.result.world),
            actions=[
                WorldActionInfo(
                    id=action.id,
                    clock_tick=action.clock_tick,
                    actor_id=action.actor_id,
                    action_type=to_public_action_type(action.action_type),
                    target_kind=action.target_kind,
                    target_id=action.target_id,
                    reason=action.reason_code,
                    run_id=action.run_id,
                    proposal_id=action.proposal_id,
                    world_version=action.world_version,
                    status=action.status,
                    world_time=action.world_time,
                )
                for action in persisted.actions
            ],
            events=[
                WorldEventInfo.model_validate(event)
                for event in persisted.events
            ],
        )
        if self._cognition is not None:
            try:
                self._cognition.catch_up_world(persisted.result.world.id)
            except CognitionProjectionError:
                logger.warning("Post-commit cognition projection failed", extra={"category": "core_projection"})
        return result

    def _plan(self, snapshot: WorldSnapshot, runtime_mode: RuntimeMode) -> dict[str, PlanningOutcome]:
        """逐 NPC 产出规划结果。任何单个 NPC 规划失败都只影响该 NPC。

        spec §13 唯一不变量：规划层出任何问题，世界都要能推进 —— 缺席的 NPC
        由 orchestrator 走确定性 decide_action。
        """
        if runtime_mode is RuntimeMode.DETERMINISTIC or self._planner is None:
            return {}
        try:
            return self._planner.decide_many(snapshot, snapshot.npcs, last_outcome=None)
        except Exception:
            # `decide_many` 已经逐 NPC 隔离了失败，走到这里说明是它整体崩了。
            logger.warning(
                "Planning failed; falling back to the deterministic policy",
                extra={"category": "planning"},
            )
            return {}
