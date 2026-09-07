from pathlib import Path
import os

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
    "agent_runs",
    "action_proposals",
    "agent_trace_entries",
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
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0003"


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
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0003"


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
    command.upgrade(config, "0002")

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
    command.upgrade(config, "0002")
    assert {constraint["name"] for constraint in inspect(engine).get_unique_constraints("actions")} == {
        "uq_actions_world_clock_tick_actor"
    }


def test_0003_backfills_legacy_groups_and_canonicalizes_actions(tmp_path):
    url = f"sqlite:///{(tmp_path / 'history.db').as_posix()}"
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "0002")
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO world_state VALUES ('w','World',1,'10:00',2,2,3)"))
        conn.execute(text("INSERT INTO locations VALUES ('park','Park','Park',0)"))
        conn.execute(text("INSERT INTO npc_profiles VALUES ('a','A','Guard','[]',1), ('b','B','Guard','[]',0)"))
        conn.execute(text("INSERT INTO npc_states VALUES ('a','park','social',50,50,50)"))
        conn.execute(text("INSERT INTO actions (id,world_id,clock_tick,actor_id,action_type,reason,status,world_time) VALUES (10,'w',1,'a','social','social_need','recorded','09:00'), (20,'w',1,'b','work','routine','recorded','09:00'), (30,'w',2,'a','rest','energy','recorded','10:00')"))
        conn.execute(text("INSERT INTO events (id,world_id,clock_tick,event_type,actor_id,action_id,description,world_time) VALUES (4,'w',1,'npc_action','a',10,'Old talk','09:00'), (8,'w',1,'npc_action','b',20,'Old work','09:00'), (12,'w',2,'npc_action','a',30,'Old rest','10:00')"))
    command.upgrade(config, "head")
    assert "agent_runs" in inspect(engine).get_table_names()
    with engine.connect() as conn:
        assert conn.execute(text("SELECT mode,status,base_clock_tick,resulting_clock_tick FROM agent_runs ORDER BY resulting_clock_tick")).all() == [("deterministic","completed",0,1),("deterministic","completed",1,2)]
        assert conn.execute(text("SELECT actor_id,ordinal FROM action_proposals ORDER BY id")).all() == [("b",0),("a",1),("a",0)]
        assert conn.execute(text("SELECT action_type,status,reason_code FROM actions ORDER BY id")).all() == [("talk","executed","social_need"),("work","executed","routine"),("rest","executed","energy")]
        assert conn.execute(text("SELECT event_sequence,description,world_time FROM events ORDER BY id")).all() == [(1,"Old talk","09:00"),(2,"Old work","09:00"),(3,"Old rest","10:00")]
        assert conn.scalar(text("SELECT current_action FROM npc_states")) == "talk"
        assert conn.scalar(text("SELECT COUNT(*) FROM events e JOIN actions a ON e.action_id=a.id JOIN agent_runs r ON e.run_id=r.id JOIN action_proposals p ON a.proposal_id=p.id WHERE a.run_id=r.id AND p.run_id=r.id")) == 3
        assert conn.scalar(text("SELECT COUNT(DISTINCT created_at) FROM events")) == 1
        assert conn.execute(text("PRAGMA foreign_key_check")).all() == []
        assert conn.scalar(text("SELECT event_sequence FROM world_state")) == 3


@pytest.mark.skipif(not os.getenv("ALERIA_TEST_POSTGRES_URL"), reason="opt-in empty PostgreSQL database required")
def test_postgresql_empty_database_upgrades_to_runtime_head():
    """Opt-in URL must point at a dedicated empty database with vector available.

    This test does not delete an existing schema or provision a server. Migration
    0002 requires permission to CREATE EXTENSION vector on that test database.
    """
    url = os.environ["ALERIA_TEST_POSTGRES_URL"]
    engine = create_engine(url)
    assert engine.dialect.name == "postgresql"
    assert inspect(engine).get_table_names() == []
    upgrade_schema(url)
    assert set(inspect(engine).get_table_names()) == MODEL_TABLES | {"alembic_version"}
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "0003"
    checks = inspect(engine).get_check_constraints("actions")
    assert not any("action_type" in check["sqltext"] for check in checks)
