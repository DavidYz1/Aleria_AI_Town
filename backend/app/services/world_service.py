from backend.app.database.world_repository import WorldRepository
from backend.app.schemas.world import (
    LocationInfo,
    NpcInfo,
    NpcStatus,
    WorldData,
    WorldInfo,
)


class WorldService:
    def __init__(self, repository: WorldRepository) -> None:
        self._repository = repository

    def get_world(self) -> WorldData:
        records = self._repository.get_world_records()
        return WorldData(
            world=WorldInfo(
                id=records.world.id,
                name=records.world.name,
                day=records.world.day,
                time=records.world.time,
                tick=records.world.tick,
            ),
            locations=[
                LocationInfo(
                    id=location.id,
                    name=location.name,
                    description=location.description,
                )
                for location in records.locations
            ],
            npcs=[
                NpcInfo(
                    id=profile.id,
                    name=profile.name,
                    role=profile.role,
                    personality=profile.personality_json,
                    location_id=state.location_id,
                    current_action=state.current_action,
                    status=NpcStatus(
                        energy=state.energy,
                        mood=state.mood,
                        social=state.social,
                    ),
                )
                for profile, state in records.npcs
            ],
        )
