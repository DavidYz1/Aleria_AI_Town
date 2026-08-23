from dataclasses import dataclass
from typing import Literal


ActionType = Literal["move", "rest", "work", "eat", "social"]
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
    tick: int
    locations: tuple[LocationSnapshot, ...]
    npcs: tuple[NpcSnapshot, ...]


@dataclass(frozen=True)
class ActionPlan:
    actor_id: str
    action_type: ActionType
    target_kind: TargetKind | None = None
    target_id: str | None = None
    reason: str = ""


@dataclass(frozen=True)
class EventPlan:
    actor_id: str
    event_type: str
    description: str


@dataclass(frozen=True)
class TickResult:
    world: WorldSnapshot
    actions: tuple[ActionPlan, ...]
    events: tuple[EventPlan, ...]
