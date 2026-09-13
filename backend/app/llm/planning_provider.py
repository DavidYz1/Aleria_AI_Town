from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from backend.app.agents.planning_contracts import AgentDecision, PlanStep


class PlanningRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    npc_id: str = Field(min_length=1, max_length=64)
    context_text: str = Field(min_length=1, max_length=12000)
    tool_manifest: list[dict] = Field(default_factory=list)
    timeout_seconds: float = Field(default=8, gt=0, le=30)


class PlanningProviderError(RuntimeError):
    """规划 provider 不可用或返回不可解析的结果。"""


class PlanningProvider(Protocol):
    def plan(self, request: PlanningRequest) -> AgentDecision: ...


class FakePlanningProvider:
    """确定性替身：不调外部服务，输出只取决于 npc_id。"""

    provider_name = "fake"
    model_name = "fake-planner-1"
    last_tokens_used = None

    def plan(self, request: PlanningRequest) -> AgentDecision:
        return AgentDecision(
            thought=f"{request.npc_id} 正在评估当前状态与近期记忆",
            goal="维持日常节奏并保持体力",
            goal_reason="确定性替身不依赖世界状态，输出恒定",
            steps=(
                PlanStep(action_type="rest", target_kind=None, target_id=None, intent="原地休息恢复体力"),
                PlanStep(action_type="work", target_kind=None, target_id=None, intent="处理本职工作"),
            ),
            prompt_version="planning-v1",
        )
