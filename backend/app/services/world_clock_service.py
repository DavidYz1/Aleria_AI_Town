import logging
from uuid import uuid4

from backend.app.agents.orchestrator import run_deterministic_advance
from backend.app.schemas.agent_run import AgentRunSummary
from backend.app.database.action_compat import to_public_action_type
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
from backend.app.world.types import WorldSnapshot
from backend.app.services.cognition_projection import CognitionProjectionError, CognitionProjectionService


logger = logging.getLogger(__name__)


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
    def __init__(self, repository: WorldTickRepository, cognition: CognitionProjectionService | None = None) -> None:
        self._repository = repository
        self._cognition = cognition

    def advance(self, expected_world_version: int) -> WorldTickData:
        snapshot = self._repository.get_snapshot()
        if snapshot.world_version != expected_world_version:
            raise WorldTickConflictError("world version conflict; refresh and retry")

        persisted = self._repository.persist_run(
            str(uuid4()), expected_world_version, run_deterministic_advance(snapshot),
            correlation_id=str(uuid4()),
        )
        result = WorldTickData(
            run=AgentRunSummary.model_validate(persisted.run),
            world=snapshot_to_world_data(persisted.result.world),
            actions=[
                WorldActionInfo(
                    id=action.id,
                    clock_tick=action.clock_tick,
                    actor_id=action.actor_id,
                    action_type=to_public_action_type(action.action_type),
                    target_kind=action.target_kind,
                    target_id=action.target_id,
                    reason=action.reason_code,
                    run_id=action.run_id,
                    proposal_id=action.proposal_id,
                    world_version=action.world_version,
                    status=action.status,
                    world_time=action.world_time,
                )
                for action in persisted.actions
            ],
            events=[
                WorldEventInfo.model_validate(event)
                for event in persisted.events
            ],
        )
        if self._cognition is not None:
            try:
                self._cognition.catch_up_world(persisted.result.world.id)
            except CognitionProjectionError:
                logger.warning("Post-commit cognition projection failed", extra={"category": "core_projection"})
        return result
