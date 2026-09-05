import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError

from backend.app.core.config import get_settings
from backend.app.database.connection import create_engine_and_session

LEGACY_REVISION = "0001"
LEGACY_TABLES = frozenset(
    {
        "world_state",
        "locations",
        "npc_profiles",
        "npc_states",
        "player_states",
        "quest_progress",
        "quest_events",
        "actions",
        "events",
        "conversations",
        "conversation_messages",
    }
)


def _alembic_config(database_url: str) -> Config:
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def upgrade_schema(database_url: str, revision: str = "head") -> None:
    engine, _ = create_engine_and_session(database_url)
    tables = set(inspect(engine).get_table_names())
    config = _alembic_config(database_url)
    if "alembic_version" not in tables and tables:
        if tables != LEGACY_TABLES:
            raise RuntimeError("database schema is partial or unsupported")
        command.stamp(config, LEGACY_REVISION)
    command.upgrade(config, revision)


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
