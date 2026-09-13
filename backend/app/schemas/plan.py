from pydantic import BaseModel, ConfigDict


class PlanStepInfo(BaseModel):
    action_type: str
    target_kind: str | None = None
    target_id: str | None = None
    intent: str


class PlanInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    goal: str
    goal_reason: str
    thought: str
    steps: list[PlanStepInfo]
    current_step_index: int
    status: str
    created_clock_tick: int
    provider: str
    model: str
    latency_ms: int | None = None
    tokens_used: int | None = None


class NpcPlanData(BaseModel):
    current: PlanInfo | None = None
    recent: list[PlanInfo] = []
