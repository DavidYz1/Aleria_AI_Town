from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
import math
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

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


class BeliefDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always")
    statement: str = Field(min_length=1, max_length=800)
    safe_summary: str = Field(min_length=1, max_length=800)
    confidence: float = Field(ge=0, le=1)
    supporting_memory_ids: tuple[UUID, ...] = Field(min_length=1, max_length=12)
    contradicting_memory_ids: tuple[UUID, ...] = Field(default=(), max_length=12)
    supersedes_belief_id: UUID | None = None
    prior_belief_disposition: Literal["superseded", "disputed"] | None = None

    @model_validator(mode="after")
    def consistent_evidence_and_revision(self):
        supporting, contradicting = self.supporting_memory_ids, self.contradicting_memory_ids
        if (len(set(supporting)) != len(supporting) or len(set(contradicting)) != len(contradicting)
                or set(supporting) & set(contradicting)
                or (self.supersedes_belief_id is None) != (self.prior_belief_disposition is None)):
            raise ValueError("invalid belief evidence or revision")
        return self


class ReflectionDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always")
    insight: str = Field(min_length=1, max_length=800)
    confidence: float = Field(ge=0, le=1)
    evidence_memory_ids: tuple[UUID, ...] = Field(min_length=1, max_length=12)
    belief: BeliefDraft | None = None
    provider: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=200)
    prompt_version: Literal["reflection-v1"]

    @model_validator(mode="after")
    def unique_evidence(self):
        if len(set(self.evidence_memory_ids)) != len(self.evidence_memory_ids):
            raise ValueError("invalid reflection evidence")
        return self


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
