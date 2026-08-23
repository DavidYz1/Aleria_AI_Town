from typing import Literal

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
    tick: int = Field(ge=0)
    time_phase: Literal["morning", "day", "evening", "night"]


class NpcRecentAction(BaseModel):
    id: int
    tick: int = Field(ge=1)
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
