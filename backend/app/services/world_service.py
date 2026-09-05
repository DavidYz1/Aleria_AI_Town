from backend.app.database.action_compat import to_public_action_type
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
                world_version=records.world.world_version,
                clock_tick=records.world.clock_tick,
                event_sequence=records.world.event_sequence,
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
                    current_action=to_public_action_type(state.current_action),
                    status=NpcStatus(
                        energy=state.energy,
                        mood=state.mood,
                        social=state.social,
                    ),
                )
                for profile, state in records.npcs
            ],
        )
