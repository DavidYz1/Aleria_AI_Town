from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator


ActionId = Literal["move", "rest", "work", "eat", "social"]
NeedValue = Annotated[int, Field(ge=0, le=100)]


class SeedWorld(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str = Field(min_length=1)
    day: int = Field(ge=1)
    time: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    tick: int = Field(ge=0)


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


class SeedData(BaseModel):
    world: SeedWorld
    locations: list[SeedLocation] = Field(min_length=1)
    npcs: list[SeedNpc] = Field(min_length=1)

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

        location_ids = {location.id for location in self.locations}
        for npc in self.npcs:
            if npc.state.location_id not in location_ids:
                errors.append(
                    f"NPC '{npc.id}' references unknown location_id "
                    f"'{npc.state.location_id}'"
                )

        if errors:
            raise ValueError("; ".join(errors))
        return self
