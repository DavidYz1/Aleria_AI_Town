from dataclasses import dataclass
import logging

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.database.models import (
    Event,
    Location,
    NpcProfile,
    NpcState,
    WorldAction,
    WorldState,
)
from backend.app.database.world_repository import (
    CANONICAL_WORLD_ID,
    WorldUnavailableError,
)
from backend.app.world.types import (
    LocationSnapshot,
    NpcSnapshot,
    TickResult,
    WorldSnapshot,
)


logger = logging.getLogger(__name__)
REQUIRED_LOCATION_IDS = {"tavern", "park"}
REQUIRED_NPC_IDS = {"ryan", "shir", "grey"}


class WorldTickConflictError(RuntimeError):
    pass


class WorldTickPersistenceError(RuntimeError):
    pass


@dataclass(frozen=True)
class PersistedTick:
    result: TickResult
    actions: tuple[WorldAction, ...]
    events: tuple[Event, ...]


class WorldTickRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_snapshot(self) -> WorldSnapshot:
        try:
            world = self._session.get(WorldState, CANONICAL_WORLD_ID)
            if world is None:
                raise WorldUnavailableError("world state is unavailable")
            locations = tuple(
                LocationSnapshot(
                    id=location.id,
                    name=location.name,
                    sort_order=location.sort_order,
                    description=location.description,
                )
                for location in self._session.scalars(
                    select(Location).order_by(Location.sort_order, Location.id)
                )
            )
            profiles = list(
                self._session.scalars(
                    select(NpcProfile).order_by(
                        NpcProfile.sort_order,
                        NpcProfile.id,
                    )
                )
            )
            states_by_npc = {
                state.npc_id: state
                for state in self._session.scalars(select(NpcState))
            }
            if (
                not REQUIRED_LOCATION_IDS.issubset(
                    {location.id for location in locations}
                )
                or not REQUIRED_NPC_IDS.issubset(
                    {profile.id for profile in profiles}
                )
                or any(profile.id not in states_by_npc for profile in profiles)
            ):
                raise WorldUnavailableError("world state is unavailable")

            npcs = tuple(
                NpcSnapshot(
                    id=profile.id,
                    name=profile.name,
                    role=profile.role,
                    personality=tuple(profile.personality_json),
                    sort_order=profile.sort_order,
                    location_id=states_by_npc[profile.id].location_id,
                    current_action=states_by_npc[profile.id].current_action,
                    energy=states_by_npc[profile.id].energy,
                    mood=states_by_npc[profile.id].mood,
                    social=states_by_npc[profile.id].social,
                )
                for profile in profiles
            )
            return WorldSnapshot(
                id=world.id,
                name=world.name,
                day=world.day,
                time=world.time,
                tick=world.tick,
                locations=locations,
                npcs=npcs,
            )
        except WorldUnavailableError:
            raise
        except SQLAlchemyError as exc:
            logger.exception("Failed to load world tick snapshot", exc_info=exc)
            raise WorldUnavailableError("world state is unavailable") from None

    def persist_tick(self, expected_tick: int, result: TickResult) -> PersistedTick:
        try:
            if (
                result.world.id != CANONICAL_WORLD_ID
                or result.world.tick != expected_tick + 1
                or len(result.actions) != len(result.world.npcs)
                or len(result.events) != len(result.actions)
            ):
                raise WorldTickPersistenceError("invalid tick result")

            updated = self._session.execute(
                update(WorldState)
                .where(
                    WorldState.id == CANONICAL_WORLD_ID,
                    WorldState.tick == expected_tick,
                )
                .values(
                    day=result.world.day,
                    time=result.world.time,
                    tick=result.world.tick,
                )
            )
            if updated.rowcount != 1:
                raise WorldTickConflictError(
                    "world tick conflict; refresh and retry"
                )

            for npc in result.world.npcs:
                state = self._session.get(NpcState, npc.id)
                if state is None:
                    raise WorldTickPersistenceError(
                        f"NPC state is unavailable: {npc.id}"
                    )
                state.location_id = npc.location_id
                state.current_action = npc.current_action
                state.energy = npc.energy
                state.mood = npc.mood
                state.social = npc.social

            actions = tuple(
                WorldAction(
                    world_id=result.world.id,
                    tick=result.world.tick,
                    actor_id=action.actor_id,
                    action_type=action.action_type,
                    target_kind=action.target_kind,
                    target_id=action.target_id,
                    reason=action.reason,
                    status="recorded",
                    world_time=result.world.time,
                )
                for action in result.actions
            )
            self._session.add_all(actions)
            self._session.flush()

            events = tuple(
                Event(
                    world_id=result.world.id,
                    tick=result.world.tick,
                    event_type=event.event_type,
                    actor_id=event.actor_id,
                    action_id=action.id,
                    description=event.description,
                    world_time=result.world.time,
                )
                for action, event in zip(actions, result.events, strict=True)
            )
            self._session.add_all(events)
            self._session.commit()
            return PersistedTick(result=result, actions=actions, events=events)
        except WorldTickConflictError:
            self._session.rollback()
            raise
        except WorldTickPersistenceError:
            self._session.rollback()
            raise
        except SQLAlchemyError as exc:
            self._session.rollback()
            logger.exception("Failed to persist world tick", exc_info=exc)
            raise WorldTickPersistenceError("world tick persistence failed") from None
