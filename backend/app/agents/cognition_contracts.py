from dataclasses import dataclass
from typing import Literal


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
