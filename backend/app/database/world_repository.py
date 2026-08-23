from dataclasses import dataclass
import logging

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.database.models import Location, NpcProfile, NpcState, WorldState


logger = logging.getLogger(__name__)
CANONICAL_WORLD_ID = "aleria-town"


class WorldUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class WorldRecords:
    world: WorldState
    locations: list[Location]
    npcs: list[tuple[NpcProfile, NpcState]]


class WorldRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_world_records(self) -> WorldRecords:
        try:
            world = self._session.get(WorldState, CANONICAL_WORLD_ID)
            if world is None:
                raise WorldUnavailableError("world state is unavailable")

            locations = list(
                self._session.scalars(select(Location).order_by(Location.sort_order))
            )
            npcs = [
                (profile, state)
                for profile, state in self._session.execute(
                    select(NpcProfile, NpcState)
                    .join(NpcState, NpcState.npc_id == NpcProfile.id)
                    .order_by(NpcProfile.sort_order)
                ).all()
            ]
            return WorldRecords(world=world, locations=locations, npcs=npcs)
        except WorldUnavailableError:
            raise
        except SQLAlchemyError as exc:
            logger.exception("Failed to load world state from SQLite", exc_info=exc)
            raise WorldUnavailableError("world state is unavailable") from None
