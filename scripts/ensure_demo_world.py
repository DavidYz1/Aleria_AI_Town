import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from backend.app.core.config import get_settings
from backend.app.database.connection import create_engine_and_session
from backend.app.database.models import Base, WorldState
from backend.app.services.demo_reset_service import (
    DemoResetPersistenceError,
    DemoResetService,
    load_seed_data,
)


def ensure_demo_world(database_url: str, seed_dir: Path) -> bool:
    seed = load_seed_data(seed_dir)
    engine, session_factory = create_engine_and_session(database_url)
    Base.metadata.create_all(engine)

    with session_factory() as session:
        if session.get(WorldState, seed.world.id) is not None:
            return False
        DemoResetService(session).reset(seed)
    return True


def main() -> int:
    try:
        initialized = ensure_demo_world(
            get_settings().database_url,
            REPO_ROOT / "data",
        )
    except (
        OSError,
        json.JSONDecodeError,
        ValidationError,
        SQLAlchemyError,
        DemoResetPersistenceError,
    ) as exc:
        print(f"Failed to ensure the Aleria demo world: {exc}", file=sys.stderr)
        return 1

    if initialized:
        print("Initialized the empty Aleria database with Demo seed data.")
    else:
        print("Existing Aleria world state preserved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
