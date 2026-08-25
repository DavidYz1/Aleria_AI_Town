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
from backend.app.database.models import Base
from backend.app.services.demo_reset_service import (
    DemoResetPersistenceError,
    DemoResetService,
    load_seed_data,
)


def seed_database(database_url: str, seed_dir: Path) -> None:
    seed = load_seed_data(seed_dir)
    engine, session_factory = create_engine_and_session(database_url)
    Base.metadata.create_all(engine)

    with session_factory() as session:
        DemoResetService(session).reset(seed)


def main() -> int:
    try:
        seed_database(get_settings().database_url, REPO_ROOT / "data")
    except (
        OSError,
        json.JSONDecodeError,
        ValidationError,
        SQLAlchemyError,
        DemoResetPersistenceError,
    ) as exc:
        print(f"Failed to seed Aleria world: {exc}", file=sys.stderr)
        return 1

    print("Seeded Aleria world into SQLite.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
