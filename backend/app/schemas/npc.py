from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from backend.app.schemas.world import ActionId, NpcStatus


class NpcProfileDetail(BaseModel):
    id: str
    name: str
    role: str
    personality: list[str]


class NpcStateDetail(BaseModel):
    location_id: str
    location_name: str
    current_action: ActionId
    status: NpcStatus


class NpcWorldContext(BaseModel):
    day: int = Field(ge=1)
    time: str
    clock_tick: int = Field(ge=0)
    time_phase: Literal["morning", "day", "evening", "night"]


class NpcRecentAction(BaseModel):
    id: int
    clock_tick: int = Field(ge=1)
    world_time: str
    action_type: ActionId
    target_kind: Literal["location", "npc"] | None
    target_id: str | None
    target_name: str | None
    reason_code: str
    reason_text: str


class NpcDetailData(BaseModel):
    profile: NpcProfileDetail
    state: NpcStateDetail
    world_context: NpcWorldContext
    recent_actions: list[NpcRecentAction]


class MemoryExplanationSource(BaseModel):
    kind: Literal[
        "world_event",
        "conversation",
        "authored_knowledge",
        "reflection",
    ]
    label: str = Field(min_length=1, max_length=40)


class MemoryExplanationItem(BaseModel):
    id: UUID
    type: Literal["episodic", "conversation", "reflection", "knowledge"]
    summary: str = Field(min_length=1, max_length=240)
    occurred_clock_tick: int = Field(ge=0)
    source: MemoryExplanationSource
    reason_text: str = Field(min_length=1, max_length=120)


class NpcMemoryExplanationsData(BaseModel):
    npc_id: str
    retrieval_mode: Literal["hybrid", "lexical_fallback"]
    fallback_used: bool
    memories: list[MemoryExplanationItem] = Field(max_length=5)
