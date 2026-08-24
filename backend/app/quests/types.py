from dataclasses import dataclass
from typing import Literal


QuestStatus = Literal[
    "available",
    "accepted",
    "briefed_by_grey",
    "shoe_found",
    "child_found",
    "completed",
]
QuestInteraction = Literal[
    "accept_quest",
    "ask_grey",
    "inspect_shoe",
    "search_child",
    "return_child",
]


class QuestStateConflictError(RuntimeError):
    pass


class QuestInteractionUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class QuestSnapshot:
    quest_id: str
    status: QuestStatus
    version: int
    player_location_id: str
    world_tick: int


@dataclass(frozen=True)
class QuestCommand:
    interaction: QuestInteraction
    expected_version: int


@dataclass(frozen=True)
class QuestTransition:
    from_status: QuestStatus
    to_status: QuestStatus
    interaction: QuestInteraction
    location_id: str
    event_text_code: str


@dataclass(frozen=True)
class QuestAvailableInteraction:
    id: QuestInteraction
    label: str


@dataclass(frozen=True)
class QuestPresentation:
    title: str
    objective: str
    available_interactions: tuple[QuestAvailableInteraction, ...]
