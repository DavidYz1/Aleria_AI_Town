from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from scripts.upgrade_schema import upgrade_schema
from tests.backend.legacy_sqlite_factory import create_unnamed_legacy_sqlite


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

COGNITION_TABLES = {
    "agent_cognition_states",
    "observations",
    "memories",
    "memory_evidence",
    "beliefs",
    "belief_evidence",
}

STAGE3M_TABLES = {
    "agent_plans",
}


def test_empty_sqlite_database_upgrades_to_head_with_model_tables(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{(tmp_path / 'empty.db').as_posix()}"

    upgrade_schema(database_url)

    engine = create_engine(database_url)
    assert set(inspect(engine).get_table_names()) == MODEL_TABLES | COGNITION_TABLES | STAGE3M_TABLES | {
        "alembic_version"
    }
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0006"


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
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0006"


def test_partial_unversioned_schema_is_rejected(tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'partial.db').as_posix()}"
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE only_one_table (id INTEGER PRIMARY KEY)"))

    with pytest.raises(RuntimeError, match="database schema is partial or unsupported"):
        upgrade_schema(database_url)


@pytest.mark.parametrize("stamped_revision", [None, "0001"])
def test_real_orm_legacy_sqlite_upgrades_without_data_loss(
    tmp_path: Path,
    stamped_revision: str | None,
) -> None:
    suffix = stamped_revision or "unversioned"
    database_url = f"sqlite:///{(tmp_path / f'legacy-{suffix}.db').as_posix()}"
    sentinels = create_unnamed_legacy_sqlite(
        database_url,
        stamped_revision=stamped_revision,
    )

    upgrade_schema(database_url)

    engine = create_engine(database_url)
    inspector = inspect(engine)
    assert "tick" not in {
        column["name"] for column in inspector.get_columns("world_state")
    }
    assert {"clock_tick", "world_version", "event_sequence"}.issubset(
        column["name"] for column in inspector.get_columns("world_state")
    )
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0006"
        assert connection.execute(
            text(
                "SELECT day, time, clock_tick, world_version, event_sequence "
                "FROM world_state WHERE id=:id"
            ),
            {"id": sentinels.world_id},
        ).one() == (7, "16:00", 44, 44, 1)
        assert connection.execute(
            text(
                "SELECT location_id, current_action, energy, mood, social "
                "FROM npc_states WHERE npc_id=:id"
            ),
            {"id": sentinels.npc_id},
        ).one() == ("tavern", "talk", 72, 61, 39)
        assert connection.scalar(
            text("SELECT location_id FROM player_states WHERE id=:id"),
            {"id": sentinels.player_id},
        ) == "castle"
        assert connection.execute(
            text(
                "SELECT status, version, updated_clock_tick FROM quest_progress "
                "WHERE player_id=:player AND quest_id=:quest"
            ),
            {"player": sentinels.player_id, "quest": sentinels.quest_id},
        ).one() == ("accepted", 2, 44)
        assert connection.execute(
            text(
                "SELECT from_status, to_status, interaction, location_id, clock_tick "
                "FROM quest_events WHERE player_id=:player AND quest_id=:quest"
            ),
            {"player": sentinels.player_id, "quest": sentinels.quest_id},
        ).one() == ("locked", "accepted", "investigate", "castle", 44)
        assert connection.execute(
            text(
                "SELECT action_type, target_kind, target_id, reason_code, status, "
                "world_time FROM actions WHERE actor_id=:id"
            ),
            {"id": sentinels.npc_id},
        ).one() == (
            "talk",
            "npc",
            sentinels.player_id,
            "legacy_social",
            "executed",
            "15:00",
        )
        assert connection.execute(
            text(
                "SELECT e.event_type, e.actor_id, e.description, e.world_time "
                "FROM events e JOIN actions a ON e.action_id=a.id "
                "WHERE a.actor_id=:id"
            ),
            {"id": sentinels.npc_id},
        ).one() == (
            "npc_action",
            sentinels.npc_id,
            "Grey spoke with the player.",
            "15:00",
        )
        assert connection.execute(
            text(
                "SELECT location_id, perception_scope, participant_npc_ids_json, "
                "witness_npc_ids_json FROM events WHERE id=:id"
            ),
            {"id": sentinels.event_id},
        ).one() == (None, None, None, None)
        assert connection.scalar(
            text("SELECT created_clock_tick FROM conversations WHERE id=:id"),
            {"id": sentinels.conversation_id},
        ) == 42
        assert connection.execute(
            text(
                "SELECT role, content, emotion, provider, fallback_used, "
                "prompt_version, clock_tick FROM conversation_messages "
                "WHERE conversation_id=:id AND role='user'"
            ),
            {"id": sentinels.conversation_id},
        ).one() == (
            "user",
            "Have you seen the missing child?",
            None,
            None,
            0,
            None,
            42,
        )
        assert connection.execute(
            text(
                "SELECT turn_id, world_version, world_time "
                "FROM conversation_messages WHERE id=:id"
            ),
            {"id": sentinels.user_message_id},
        ).one() == (None, None, None)
        assert connection.execute(
            text(
                "SELECT role, content, emotion, provider, fallback_used, "
                "prompt_version, clock_tick FROM conversation_messages "
                "WHERE conversation_id=:id AND role='assistant'"
            ),
            {"id": sentinels.conversation_id},
        ).one() == (
            "assistant",
            "Ask at the castle gate.",
            "concerned",
            "legacy-provider",
            1,
            "legacy-v1",
            43,
        )
        assert connection.scalar(
            text(
                "SELECT count(*) FROM conversation_messages "
                "WHERE conversation_id=:id"
            ),
            {"id": sentinels.conversation_id},
        ) == 2
        assert not connection.execute(
            text("SELECT name FROM sqlite_master WHERE name LIKE '_alembic_tmp_%'")
        ).all()


@pytest.mark.parametrize("stamped_revision", [None, "0001"])
def test_real_orm_legacy_sqlite_preserves_unrelated_schema_objects(
    tmp_path: Path,
    stamped_revision: str | None,
) -> None:
    suffix = stamped_revision or "unversioned"
    database_url = f"sqlite:///{(tmp_path / f'legacy-check-{suffix}.db').as_posix()}"
    sentinels = create_unnamed_legacy_sqlite(
        database_url,
        stamped_revision=stamped_revision,
    )

    upgrade_schema(database_url)

    engine = create_engine(database_url)
    inspector = inspect(engine)
    assert inspector.get_pk_constraint("actions")["constrained_columns"] == ["id"]
    assert {
        (
            tuple(foreign_key["constrained_columns"]),
            foreign_key["referred_table"],
            tuple(foreign_key["referred_columns"]),
        )
        for foreign_key in inspector.get_foreign_keys("actions")
    }.issuperset(
        {
            (("world_id",), "world_state", ("id",)),
            (("actor_id",), "npc_profiles", ("id",)),
        }
    )
    assert ("action_id",) in {
        tuple(constraint["column_names"])
        for constraint in inspector.get_unique_constraints("events")
    }
    assert {
        index["name"]: tuple(index["column_names"])
        for index in inspector.get_indexes("conversation_messages")
    }["ix_conversation_messages_conversation_id_id"] == (
        "conversation_id",
        "id",
    )
    with engine.begin() as connection:
        with pytest.raises(IntegrityError):
            connection.execute(
                text("UPDATE world_state SET day=0 WHERE id=:id"),
                {"id": sentinels.world_id},
            )


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


def test_0003_foundation_data_upgrades_to_cognition_head_without_fabricated_sources(tmp_path):
    url = f"sqlite:///{(tmp_path / 'foundation-to-cognition.db').as_posix()}"
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "0003")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO world_state "
            "(id,name,day,time,clock_tick,world_version,event_sequence) "
            "VALUES ('w','World',1,'08:00',0,0,1)"
        ))
        connection.execute(text(
            "INSERT INTO locations (id,name,description,sort_order) "
            "VALUES ('castle','Castle','Stone castle',1)"
        ))
        connection.execute(text(
            "INSERT INTO npc_profiles (id,name,role,personality_json,sort_order) "
            "VALUES ('grey','Grey','Innkeeper','[]',1)"
        ))
        connection.execute(text(
            "INSERT INTO npc_states "
            "(npc_id,location_id,current_action,energy,mood,social) "
            "VALUES ('grey','castle','wait',50,50,50)"
        ))
        connection.execute(text(
            "INSERT INTO events "
            "(world_id,clock_tick,event_type,actor_id,action_id,description,world_time,"
            "run_id,world_version,event_sequence,source_event_id,payload_json,visibility,"
            "secrecy,causation_id,correlation_id,created_at) VALUES "
            "('w',0,'npc_action','grey',NULL,'Legacy event','08:00',NULL,0,1,NULL,'{}',"
            "'public','public',NULL,'00000000-0000-0000-0000-000000000001',"
            "'2026-09-09 00:00:00')"
        ))
        legacy_event_id = connection.scalar(text("SELECT id FROM events"))
        connection.execute(text(
            "INSERT INTO conversations "
            "(id,world_id,npc_id,created_clock_tick,created_at,updated_at) VALUES "
            "('conversation','w','grey',0,'2026-09-09 00:00:00','2026-09-09 00:00:00')"
        ))
        connection.execute(text(
            "INSERT INTO conversation_messages "
            "(conversation_id,role,content,emotion,provider,fallback_used,prompt_version,"
            "clock_tick,created_at) VALUES "
            "('conversation','user','Legacy claim',NULL,NULL,0,NULL,0,'2026-09-09 00:00:00')"
        ))
        legacy_message_id = connection.scalar(text("SELECT id FROM conversation_messages"))

    command.upgrade(config, "head")

    assert COGNITION_TABLES.issubset(inspect(engine).get_table_names())
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0006"
        assert connection.execute(text(
            "SELECT location_id, perception_scope, participant_npc_ids_json, "
            "witness_npc_ids_json FROM events WHERE id=:id"
        ), {"id": legacy_event_id}).one() == (None, None, None, None)
        assert connection.execute(text(
            "SELECT turn_id, world_version, world_time FROM conversation_messages "
            "WHERE id=:id"
        ), {"id": legacy_message_id}).one() == (None, None, None)


def test_postgresql_empty_database_upgrades_to_runtime_head(postgres_database_url):
    """Migrate an isolated empty schema; vector extension permission is required."""
    url = postgres_database_url
    engine = create_engine(url)
    try:
        assert engine.dialect.name == "postgresql"
        assert inspect(engine).get_table_names() == []
        upgrade_schema(url)
        assert set(inspect(engine).get_table_names()) == MODEL_TABLES | COGNITION_TABLES | STAGE3M_TABLES | {"alembic_version"}
        with engine.connect() as conn:
            assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "0006"
        checks = inspect(engine).get_check_constraints("actions")
        assert not any("action_type" in check["sqltext"] for check in checks)
    finally:
        engine.dispose()


def test_0005_agent_plans_upgrade_is_idempotent_and_preserves_rows(tmp_path: Path) -> None:
    """AGENTS.md 要求每次结构变更覆盖「重复运行幂等」。

    空库升级到 head 与已有库原地升级保留数据已由本文件其他测试泛化覆盖，
    重复运行此前无覆盖。这里连同 agent_plans 的真实行一起验证。
    """
    database_url = f"sqlite:///{(tmp_path / 'idempotent.db').as_posix()}"
    upgrade_schema(database_url)

    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO world_state (id, name, day, time, clock_tick, world_version, event_sequence)"
            " VALUES ('aleria-town', 'w', 1, '08:00', 0, 0, 0)"
        ))
        connection.execute(text(
            "INSERT INTO npc_profiles (id, name, role, personality_json, sort_order)"
            " VALUES ('elena', 'Elena', 'Knight', '[]', 1)"
        ))
        connection.execute(text(
            "INSERT INTO agent_plans (id, world_id, owner_npc_id, thought, goal, goal_reason,"
            " steps_json, current_step_index, status, created_clock_tick, updated_clock_tick,"
            " provider, model, prompt_version)"
            " VALUES ('plan-1', 'aleria-town', 'elena', 't', 'g', 'r', '[]', 0, 'active', 1, 1,"
            " 'fake', 'fake-1', 'planning-v1')"
        ))

    tables_before = set(inspect(engine).get_table_names())

    upgrade_schema(database_url)

    assert set(inspect(engine).get_table_names()) == tables_before
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0006"
        assert connection.scalar(text("SELECT count(*) FROM agent_plans")) == 1, (
            "非空前提：重复升级后计划行必须仍在"
        )
        assert connection.scalar(text("SELECT status FROM agent_plans WHERE id = 'plan-1'")) == "active"


def test_0006_plan_evidence_upgrades_in_place_and_leaves_legacy_rows_unknown(
    tmp_path: Path,
) -> None:
    """`0006` 给 `agent_plans` 补记录本次规划引用了哪些记忆的列。

    列必须可空且**不带 server_default**：`0006` 之前写入的计划确实没有这份记录，
    默认成空数组等于声称「它引用了 0 条记忆」—— 那是一条无法支撑的断言，
    UI 会把「未记录」渲染成「什么都没引用」。两者必须可区分。
    """
    database_url = f"sqlite:///{(tmp_path / 'evidence.db').as_posix()}"
    upgrade_schema(database_url)

    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO world_state (id, name, day, time, clock_tick, world_version, event_sequence)"
            " VALUES ('aleria-town', 'w', 1, '08:00', 0, 0, 0)"
        ))
        connection.execute(text(
            "INSERT INTO npc_profiles (id, name, role, personality_json, sort_order)"
            " VALUES ('elena', 'Elena', 'Knight', '[]', 1)"
        ))
        connection.execute(text(
            "INSERT INTO agent_plans (id, world_id, owner_npc_id, thought, goal, goal_reason,"
            " steps_json, current_step_index, status, created_clock_tick, updated_clock_tick,"
            " provider, model, prompt_version)"
            " VALUES ('legacy-plan', 'aleria-town', 'elena', 't', 'g', 'r', '[]', 0, 'active', 1, 1,"
            " 'fake', 'fake-1', 'planning-v1')"
        ))

    tables_before = set(inspect(engine).get_table_names())
    upgrade_schema(database_url)  # 重复运行必须幂等

    assert set(inspect(engine).get_table_names()) == tables_before
    columns = {c["name"] for c in inspect(engine).get_columns("agent_plans")}
    assert "evidence_memory_ids_json" in columns

    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0006"
        # 非空前提：升级前写入的那一行必须还在，否则下面的断言无从谈起。
        assert connection.scalar(text("SELECT count(*) FROM agent_plans")) == 1
        assert connection.scalar(text(
            "SELECT evidence_memory_ids_json FROM agent_plans WHERE id = 'legacy-plan'"
        )) is None, "历史行必须读作「未记录」，不能被默认成空数组"
