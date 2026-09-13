from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ACTION_TYPES = Literal["move", "work", "eat", "talk", "rest", "wait"]


class PlanStep(BaseModel):
    model_config = ConfigDict(frozen=True)

    action_type: ACTION_TYPES
    target_kind: Literal["location", "npc"] | None = None
    target_id: str | None = None
    intent: str = Field(min_length=1, max_length=200)


class AgentDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    thought: str = Field(min_length=1, max_length=800)
    goal: str = Field(min_length=1, max_length=200)
    goal_reason: str = Field(min_length=1, max_length=500)
    steps: tuple[PlanStep, ...] = Field(min_length=1, max_length=4)
    prompt_version: Literal["planning-v1"]
