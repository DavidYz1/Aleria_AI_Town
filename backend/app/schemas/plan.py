from pydantic import BaseModel, ConfigDict


class PlanStepInfo(BaseModel):
    action_type: str
    target_kind: str | None = None
    target_id: str | None = None
    intent: str


class PlanEvidenceItem(BaseModel):
    """一条本次规划引用过、且允许对玩家公开的记忆。"""

    id: str
    type: str
    label: str
    summary: str


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
    # 只含通过公开硬过滤的记忆。计划落盘的引用是完整的，但不可公开的那些
    # 既不出现内容，也不以计数或占位符暴露 —— 与 memory-explanations 同一规则。
    evidence: list[PlanEvidenceItem] = []


class NpcPlanData(BaseModel):
    current: PlanInfo | None = None
    recent: list[PlanInfo] = []
