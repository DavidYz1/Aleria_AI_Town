from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.agents.planning_contracts import AgentDecision
from backend.app.database.models import AgentPlan


class PlanRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_active(self, world_id: str, npc_id: str) -> AgentPlan | None:
        statement = select(AgentPlan).where(
            AgentPlan.world_id == world_id,
            AgentPlan.owner_npc_id == npc_id,
            AgentPlan.status == "active",
        )
        return self._session.scalars(statement).one_or_none()

    def create_from_decision(
        self, world_id: str, npc_id: str, decision: AgentDecision, *,
        clock_tick: int, run_id: str | None, provider: str, model: str,
        latency_ms: int | None, tokens_used: int | None,
    ) -> AgentPlan:
        plan = AgentPlan(
            id=str(uuid4()), world_id=world_id, owner_npc_id=npc_id, source_run_id=run_id,
            thought=decision.thought, goal=decision.goal, goal_reason=decision.goal_reason,
            steps_json=[step.model_dump() for step in decision.steps],
            current_step_index=0, status="active",
            created_clock_tick=clock_tick, updated_clock_tick=clock_tick,
            provider=provider, model=model, prompt_version=decision.prompt_version,
            latency_ms=latency_ms, tokens_used=tokens_used,
        )
        self._session.add(plan)
        self._session.flush()
        return plan

    def advance_step(self, plan: AgentPlan, *, clock_tick: int) -> AgentPlan:
        plan.current_step_index += 1
        plan.updated_clock_tick = clock_tick
        if plan.current_step_index >= len(plan.steps_json):
            plan.status = "completed"
        self._session.flush()
        return plan

    def abandon(self, plan: AgentPlan, *, clock_tick: int) -> AgentPlan:
        plan.status = "abandoned"
        plan.updated_clock_tick = clock_tick
        self._session.flush()
        return plan

    def recent(self, world_id: str, npc_id: str, *, limit: int) -> list[AgentPlan]:
        statement = (
            select(AgentPlan)
            .where(AgentPlan.world_id == world_id, AgentPlan.owner_npc_id == npc_id)
            .order_by(AgentPlan.created_clock_tick.desc(), AgentPlan.id.desc())
            .limit(limit)
        )
        return list(self._session.scalars(statement))
