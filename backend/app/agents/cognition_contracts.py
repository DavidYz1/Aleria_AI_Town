from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
import math
from typing import Literal

from backend.app.agents.contracts import JsonValue, _freeze_json_object


EventPerceptionScope = Literal[
    "world_public",
    "location",
    "participants",
    "professional",
    "private",
]


@dataclass(frozen=True)
class EventPerceptionMetadata:
    location_id: str | None
    perception_scope: EventPerceptionScope
    participant_npc_ids: tuple[str, ...]
    witness_npc_ids: tuple[str, ...]
    professional_channels: tuple[str, ...]
    attention_priority: float
    is_critical: bool


class SourceKind(StrEnum):
    EVENT = "event"
    CONVERSATION_TURN = "conversation_turn"
    AUTHORED_KNOWLEDGE = "authored_knowledge"


class PerceptionMode(StrEnum):
    PARTICIPANT = "participant"
    WITNESSED = "witnessed"
    PROFESSIONAL_CHANNEL = "professional_channel"
    DIRECT_DIALOGUE = "direct_dialogue"


@dataclass(frozen=True)
class ObservationDraft:
    owner_npc_id: str
    source_kind: SourceKind
    source_key: str
    policy_version: str
    perception_mode: PerceptionMode
    summary: str
    facts: Mapping[str, JsonValue]
    related_entity_ids: tuple[str, ...]
    secrecy: Literal["public", "private", "secret"]
    disclosure_scope: Literal["public", "player_dialogue", "internal_only"]
    importance: float
    confidence: float
    emotional_valence: float
    is_critical: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "facts", _freeze_json_object(self.facts))
        object.__setattr__(self, "related_entity_ids", tuple(self.related_entity_ids))
        for value, low, high in ((self.importance, 0, 1), (self.confidence, 0, 1),
                                 (self.emotional_valence, -1, 1)):
            if not math.isfinite(value) or not low <= value <= high:
                raise ValueError("invalid cognition score")
