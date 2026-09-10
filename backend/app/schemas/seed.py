from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator


ActionId = Literal["eat", "move", "rest", "talk", "wait", "work"]
NeedValue = Annotated[int, Field(ge=0, le=100)]
Score = Annotated[float, Field(ge=0, le=1)]
EmotionalValence = Annotated[float, Field(ge=-1, le=1)]


class SeedWorld(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str = Field(min_length=1)
    day: int = Field(ge=1)
    time: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    world_version: int = Field(ge=0)
    clock_tick: int = Field(ge=0)
    event_sequence: int = Field(ge=0)


class SeedLocation(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    sort_order: int = Field(ge=1)


class SeedNpcStatus(BaseModel):
    location_id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    current_action: ActionId
    energy: NeedValue
    mood: NeedValue
    social: NeedValue


class SeedNpc(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str = Field(min_length=1)
    role: str = Field(min_length=1)
    personality: list[str] = Field(min_length=1)
    sort_order: int = Field(ge=1)
    state: SeedNpcStatus


class SeedAuthoredKnowledge(BaseModel):
    source_id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    owner_npc_id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    content: str = Field(min_length=1)
    safe_summary: str = Field(min_length=1)
    secrecy: Literal["public", "private", "secret"]
    disclosure_scope: Literal["public", "player_dialogue", "internal_only"]
    importance: Score
    confidence: Score
    emotional_valence: EmotionalValence
    occurred_world_version: int = Field(ge=0)
    occurred_clock_tick: int = Field(ge=0)
    occurred_world_time: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    source_created_at: datetime


class SeedData(BaseModel):
    world: SeedWorld
    locations: list[SeedLocation] = Field(min_length=1)
    npcs: list[SeedNpc] = Field(min_length=1)
    authored_knowledge_version: str = Field(min_length=1)
    authored_knowledge: list[SeedAuthoredKnowledge] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_relations(self):
        errors: list[str] = []

        def find_duplicates(values: list[str | int]) -> list[str | int]:
            seen: set[str | int] = set()
            duplicates: list[str | int] = []
            for value in values:
                if value in seen and value not in duplicates:
                    duplicates.append(value)
                seen.add(value)
            return duplicates

        for location_id in find_duplicates(
            [location.id for location in self.locations]
        ):
            errors.append(f"duplicate location id '{location_id}'")
        for sort_order in find_duplicates(
            [location.sort_order for location in self.locations]
        ):
            errors.append(f"duplicate location sort_order '{sort_order}'")
        for npc_id in find_duplicates([npc.id for npc in self.npcs]):
            errors.append(f"duplicate NPC id '{npc_id}'")
        for sort_order in find_duplicates([npc.sort_order for npc in self.npcs]):
            errors.append(f"duplicate NPC sort_order '{sort_order}'")
        for source_id in find_duplicates(
            [item.source_id for item in self.authored_knowledge]
        ):
            errors.append(f"duplicate authored knowledge source_id '{source_id}'")

        location_ids = {location.id for location in self.locations}
        for npc in self.npcs:
            if npc.state.location_id not in location_ids:
                errors.append(
                    f"NPC '{npc.id}' references unknown location_id "
                    f"'{npc.state.location_id}'"
                )

        npc_ids = {npc.id for npc in self.npcs}
        for item in self.authored_knowledge:
            if item.owner_npc_id not in npc_ids:
                errors.append(
                    "authored knowledge "
                    f"'{item.source_id}' references unknown owner_npc_id "
                    f"'{item.owner_npc_id}'"
                )

        if errors:
            raise ValueError("; ".join(errors))
        return self
