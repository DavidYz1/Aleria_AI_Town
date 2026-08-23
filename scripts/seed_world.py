import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pydantic import ValidationError
from sqlalchemy import delete
from sqlalchemy.exc import SQLAlchemyError

from backend.app.core.config import get_settings
from backend.app.database.connection import create_engine_and_session
from backend.app.database.models import (
    Base,
    Event,
    Location,
    NpcProfile,
    NpcState,
    WorldAction,
    WorldState,
)
from backend.app.schemas.seed import SeedData

def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_seed_data(seed_dir: Path) -> SeedData:
    return SeedData.model_validate(
        {
            "world": _read_json(seed_dir / "world.json"),
            "locations": _read_json(seed_dir / "locations.json"),
            "npcs": _read_json(seed_dir / "npcs.json"),
        }
    )


def seed_database(database_url: str, seed_dir: Path) -> None:
    seed = load_seed_data(seed_dir)
    engine, session_factory = create_engine_and_session(database_url)
    Base.metadata.create_all(engine)

    with session_factory() as session:
        session.execute(delete(Event).where(Event.world_id == seed.world.id))
        session.execute(
            delete(WorldAction).where(WorldAction.world_id == seed.world.id)
        )
        session.merge(WorldState(**seed.world.model_dump()))
        for location in seed.locations:
            session.merge(Location(**location.model_dump()))
        for npc in seed.npcs:
            session.merge(
                NpcProfile(
                    id=npc.id,
                    name=npc.name,
                    role=npc.role,
                    personality_json=npc.personality,
                    sort_order=npc.sort_order,
                )
            )
        session.flush()
        for npc in seed.npcs:
            session.merge(NpcState(npc_id=npc.id, **npc.state.model_dump()))
        session.commit()


def main() -> int:
    try:
        seed_database(get_settings().database_url, REPO_ROOT / "data")
    except (OSError, json.JSONDecodeError, ValidationError, SQLAlchemyError) as exc:
        print(f"Failed to seed Aleria world: {exc}", file=sys.stderr)
        return 1

    print("Seeded Aleria world into SQLite.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
