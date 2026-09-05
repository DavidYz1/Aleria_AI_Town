from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from scripts.upgrade_schema import upgrade_schema


MODEL_TABLES = {
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


def test_empty_sqlite_database_upgrades_to_head_with_model_tables(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{(tmp_path / 'empty.db').as_posix()}"

    upgrade_schema(database_url)

    engine = create_engine(database_url)
    assert set(inspect(engine).get_table_names()) == MODEL_TABLES | {
        "alembic_version"
    }
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0002"


def test_sqlite_url_with_percent_character_upgrades_to_head(tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'percent%database.db').as_posix()}"

    upgrade_schema(database_url)

    assert "alembic_version" in inspect(create_engine(database_url)).get_table_names()


def test_baseline_migration_names_integer_primary_keys(tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'primary-keys.db').as_posix()}"

    upgrade_schema(database_url)

    inspector = inspect(create_engine(database_url))
    assert {
        table: inspector.get_pk_constraint(table)["name"]
        for table in ("quest_events", "actions", "events", "conversation_messages")
    } == {
        "quest_events": "pk_quest_events",
        "actions": "pk_actions",
        "events": "pk_events",
        "conversation_messages": "pk_conversation_messages",
    }


def test_exact_unversioned_legacy_schema_is_adopted(tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}"
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "0001")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE alembic_version"))

    upgrade_schema(database_url)

    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0002"


def test_partial_unversioned_schema_is_rejected(tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'partial.db').as_posix()}"
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE only_one_table (id INTEGER PRIMARY KEY)"))

    with pytest.raises(RuntimeError, match="database schema is partial or unsupported"):
        upgrade_schema(database_url)


def test_0002_actions_unique_constraint_survives_upgrade_downgrade_round_trip(
    tmp_path: Path,
) -> None:
    """Dropping the actions uniqueness during a batch rename must fail."""
    database_url = f"sqlite:///{(tmp_path / 'actions-round-trip.db').as_posix()}"
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "0001")
    command.upgrade(config, "head")

    engine = create_engine(database_url)
    assert {constraint["name"] for constraint in inspect(engine).get_unique_constraints("actions")} == {
        "uq_actions_world_clock_tick_actor"
    }
    with engine.connect() as connection:
        transaction = connection.begin()
        connection.execute(
            text(
                "INSERT INTO world_state "
                "(id, name, day, time, clock_tick, world_version, event_sequence) "
                "VALUES ('world', 'World', 1, '08:00', 0, 0, 0)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO npc_profiles "
                "(id, name, role, personality_json, sort_order) "
                "VALUES ('npc', 'NPC', 'Guard', '[]', 1)"
            )
        )
        action = text(
            "INSERT INTO actions "
            "(world_id, clock_tick, actor_id, action_type, target_kind, target_id, reason, status, world_time) "
            "VALUES ('world', 1, 'npc', 'rest', NULL, NULL, 'test', 'recorded', '09:00')"
        )
        connection.execute(action)
        with pytest.raises(IntegrityError):
            connection.execute(action)
        transaction.rollback()

    command.downgrade(config, "0001")
    assert {constraint["name"] for constraint in inspect(engine).get_unique_constraints("actions")} == {
        "uq_actions_world_tick_actor"
    }
    command.upgrade(config, "head")
    assert {constraint["name"] for constraint in inspect(engine).get_unique_constraints("actions")} == {
        "uq_actions_world_clock_tick_actor"
    }
