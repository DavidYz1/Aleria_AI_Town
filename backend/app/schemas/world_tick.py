from typing import Literal

from pydantic import BaseModel, Field

from backend.app.schemas.world import ActionId, WorldData


class WorldTickRequest(BaseModel):
    expected_tick: int = Field(ge=0)


class WorldActionInfo(BaseModel):
    id: int
    tick: int = Field(ge=1)
    actor_id: str
    action_type: ActionId
    target_kind: Literal["location", "npc"] | None
    target_id: str | None
    reason: str
    status: Literal["recorded"]
    world_time: str


class WorldEventInfo(BaseModel):
    id: int
    tick: int = Field(ge=1)
    event_type: Literal["npc_action"]
    actor_id: str
    action_id: int
    description: str
    world_time: str


class WorldTickData(BaseModel):
    world: WorldData
    actions: list[WorldActionInfo]
    events: list[WorldEventInfo]
