from typing import Literal

from pydantic import BaseModel, Field


ActionId = Literal["move", "rest", "work", "eat", "social"]


class WorldInfo(BaseModel):
    id: str
    name: str
    day: int = Field(ge=1)
    time: str
    tick: int = Field(ge=0)


class LocationInfo(BaseModel):
    id: str
    name: str
    description: str


class NpcStatus(BaseModel):
    energy: int = Field(ge=0, le=100)
    mood: int = Field(ge=0, le=100)
    social: int = Field(ge=0, le=100)


class NpcInfo(BaseModel):
    id: str
    name: str
    role: str
    personality: list[str]
    location_id: str
    current_action: ActionId
    status: NpcStatus


class WorldData(BaseModel):
    world: WorldInfo
    locations: list[LocationInfo]
    npcs: list[NpcInfo]
