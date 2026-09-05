from sqlalchemy import update
from sqlalchemy.orm import Session

from backend.app.database.models import WorldState


class WorldVersionConflictError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("world version conflict; refresh and retry")


def bump_world_version(
    session: Session, world_id: str, expected_world_version: int
) -> int:
    updated = session.execute(
        update(WorldState)
        .where(
            WorldState.id == world_id,
            WorldState.world_version == expected_world_version,
        )
        .values(world_version=WorldState.world_version + 1)
    )
    if updated.rowcount != 1:
        raise WorldVersionConflictError()
    return expected_world_version + 1
