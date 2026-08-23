import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy.exc import SQLAlchemyError

from backend.app.core.config import get_settings
from backend.app.database.connection import create_engine_and_session
from backend.app.database.models import Base


def upgrade_schema(database_url: str) -> None:
    engine, _ = create_engine_and_session(database_url)
    Base.metadata.create_all(engine)


def main() -> int:
    try:
        upgrade_schema(get_settings().database_url)
    except SQLAlchemyError as exc:
        print(f"Failed to upgrade Aleria schema: {exc}", file=sys.stderr)
        return 1

    print("Aleria database schema is up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
