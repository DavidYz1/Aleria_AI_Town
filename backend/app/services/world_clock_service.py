from backend.app.database.world_clock_repository import (
    WorldTickConflictError,
    WorldTickRepository,
)
from backend.app.schemas.world import (
    LocationInfo,
    NpcInfo,
    NpcStatus,
    WorldData,
    WorldInfo,
)
from backend.app.schemas.world_clock import (
    WorldActionInfo,
    WorldEventInfo,
    WorldTickData,
)
from backend.app.world.tick_engine import run_tick
from backend.app.world.types import WorldSnapshot


def snapshot_to_world_data(snapshot: WorldSnapshot) -> WorldData:
    return WorldData(
        world=WorldInfo(
            id=snapshot.id,
            name=snapshot.name,
            day=snapshot.day,
            time=snapshot.time,
            world_version=snapshot.world_version,
            clock_tick=snapshot.clock_tick,
            event_sequence=snapshot.event_sequence,
        ),
        locations=[
            LocationInfo(
                id=location.id,
                name=location.name,
                description=location.description,
            )
            for location in snapshot.locations
        ],
        npcs=[
            NpcInfo(
                id=npc.id,
                name=npc.name,
                role=npc.role,
                personality=list(npc.personality),
                location_id=npc.location_id,
                current_action=npc.current_action,
                status=NpcStatus(
                    energy=npc.energy,
                    mood=npc.mood,
                    social=npc.social,
                ),
            )
            for npc in snapshot.npcs
        ],
    )


class WorldTickService:
    def __init__(self, repository: WorldTickRepository) -> None:
        self._repository = repository

    def advance(self, expected_world_version: int) -> WorldTickData:
        snapshot = self._repository.get_snapshot()
        if snapshot.world_version != expected_world_version:
            raise WorldTickConflictError("world version conflict; refresh and retry")

        persisted = self._repository.persist_tick(expected_world_version, run_tick(snapshot))
        return WorldTickData(
            world=snapshot_to_world_data(persisted.result.world),
            actions=[
                WorldActionInfo(
                    id=action.id,
                    clock_tick=action.clock_tick,
                    actor_id=action.actor_id,
                    action_type=action.action_type,
                    target_kind=action.target_kind,
                    target_id=action.target_id,
                    reason=action.reason,
                    status=action.status,
                    world_time=action.world_time,
                )
                for action in persisted.actions
            ],
            events=[
                WorldEventInfo(
                    id=event.id,
                    clock_tick=event.clock_tick,
                    event_type=event.event_type,
                    actor_id=event.actor_id,
                    action_id=event.action_id,
                    description=event.description,
                    world_time=event.world_time,
                )
                for event in persisted.events
            ],
        )
