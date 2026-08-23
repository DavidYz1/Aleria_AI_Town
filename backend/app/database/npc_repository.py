from dataclasses import dataclass
import logging

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.database.models import (
    Location,
    NpcProfile,
    NpcState,
    WorldAction,
    WorldState,
)
from backend.app.database.world_repository import CANONICAL_WORLD_ID


logger = logging.getLogger(__name__)


class NpcNotFoundError(RuntimeError):
    pass


class NpcDetailUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class NpcActionRecord:
    id: int
    tick: int
    world_time: str
    action_type: str
    target_kind: str | None
    target_id: str | None
    reason: str


@dataclass(frozen=True)
class NpcDetailRecords:
    profile: NpcProfile
    state: NpcState
    location: Location
    world: WorldState
    actions: tuple[NpcActionRecord, ...]
    target_names: dict[tuple[str, str], str]


class NpcRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_detail_records(self, npc_id: str) -> NpcDetailRecords:
        try:
            profile = self._session.get(NpcProfile, npc_id)
            if profile is None:
                raise NpcNotFoundError("NPC not found")

            state = self._session.get(NpcState, npc_id)
            world = self._session.get(WorldState, CANONICAL_WORLD_ID)
            if state is None or world is None:
                raise NpcDetailUnavailableError("NPC detail is unavailable")

            location = self._session.get(Location, state.location_id)
            if location is None:
                raise NpcDetailUnavailableError("NPC detail is unavailable")

            stored_actions = tuple(
                self._session.scalars(
                    select(WorldAction)
                    .where(
                        WorldAction.world_id == CANONICAL_WORLD_ID,
                        WorldAction.actor_id == npc_id,
                    )
                    .order_by(WorldAction.tick.desc(), WorldAction.id.desc())
                    .limit(3)
                )
            )
            actions = tuple(
                NpcActionRecord(
                    id=action.id,
                    tick=action.tick,
                    world_time=action.world_time,
                    action_type=action.action_type,
                    target_kind=action.target_kind,
                    target_id=action.target_id,
                    reason=action.reason,
                )
                for action in stored_actions
            )

            location_target_ids = {
                action.target_id
                for action in actions
                if action.target_kind == "location" and action.target_id is not None
            }
            npc_target_ids = {
                action.target_id
                for action in actions
                if action.target_kind == "npc" and action.target_id is not None
            }
            target_names: dict[tuple[str, str], str] = {}
            if location_target_ids:
                target_names.update(
                    {
                        ("location", target.id): target.name
                        for target in self._session.scalars(
                            select(Location).where(
                                Location.id.in_(location_target_ids)
                            )
                        )
                    }
                )
            if npc_target_ids:
                target_names.update(
                    {
                        ("npc", target.id): target.name
                        for target in self._session.scalars(
                            select(NpcProfile).where(
                                NpcProfile.id.in_(npc_target_ids)
                            )
                        )
                    }
                )

            return NpcDetailRecords(
                profile=profile,
                state=state,
                location=location,
                world=world,
                actions=actions,
                target_names=target_names,
            )
        except (NpcNotFoundError, NpcDetailUnavailableError):
            raise
        except SQLAlchemyError as exc:
            logger.exception("Failed to load NPC detail", exc_info=exc)
            raise NpcDetailUnavailableError(
                "NPC detail is unavailable"
            ) from None
