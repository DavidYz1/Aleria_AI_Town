from dataclasses import dataclass
from typing import Literal

from backend.app.agents.contracts import ActionProposal

ActionType = Literal["eat", "move", "rest", "talk", "wait", "work"]
TargetKind = Literal["location", "npc"]
TimePhase = Literal["morning", "day", "evening", "night"]


@dataclass(frozen=True)
class LocationSnapshot:
    id: str
    name: str
    sort_order: int
    description: str = ""


@dataclass(frozen=True)
class NpcSnapshot:
    id: str
    name: str
    role: str
    personality: tuple[str, ...]
    sort_order: int
    location_id: str
    current_action: ActionType
    energy: int
    mood: int
    social: int


@dataclass(frozen=True)
class WorldSnapshot:
    id: str
    name: str
    day: int
    time: str
    clock_tick: int
    world_version: int
    event_sequence: int
    locations: tuple[LocationSnapshot, ...]
    npcs: tuple[NpcSnapshot, ...]


@dataclass(frozen=True)
class EventPlan:
    actor_id: str
    event_type: str
    description: str


@dataclass(frozen=True)
class TickResult:
    world: WorldSnapshot
    actions: tuple[ActionProposal, ...]
    events: tuple[EventPlan, ...]
