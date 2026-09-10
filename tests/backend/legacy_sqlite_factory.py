from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData, Table, create_engine
from sqlalchemy.engine import make_url


LEGACY_TABLES = (
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
)


@dataclass(frozen=True)
class LegacySentinels:
    world_id: str = "aleria-town"
    npc_id: str = "grey"
    player_id: str = "default-player"
    quest_id: str = "missing-child"
    conversation_id: str = "legacy-conversation"
    event_id: int = 1
    user_message_id: int = 1
    assistant_message_id: int = 2


def _alembic_config(database_url: str) -> Config:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def create_unnamed_legacy_sqlite(
    database_url: str,
    *,
    stamped_revision: str | None,
) -> LegacySentinels:
    """Create the committed 0001 shape with ORM-style unnamed constraints."""
    target_path = Path(make_url(database_url).database or "")
    source_path = target_path.with_name(f".{target_path.name}.0001-source.db")
    source_url = f"sqlite:///{source_path.as_posix()}"
    sentinels = LegacySentinels()
    created_at = datetime(2026, 9, 8, 8, 0, tzinfo=UTC)

    command.upgrade(_alembic_config(source_url), "0001")
    source_engine = create_engine(source_url)
    target_engine = create_engine(database_url)
    try:
        metadata = MetaData()
        for table_name in LEGACY_TABLES:
            Table(table_name, metadata, autoload_with=source_engine)
        for table in metadata.tables.values():
            for constraint in table.constraints:
                constraint.name = None

        metadata.create_all(target_engine)
        tables = metadata.tables
        with target_engine.begin() as connection:
            connection.execute(
                tables["world_state"].insert(),
                {
                    "id": sentinels.world_id,
                    "name": "Aleria Town",
                    "day": 7,
                    "time": "16:00",
                    "tick": 44,
                },
            )
            connection.execute(
                tables["locations"].insert(),
                [
                    {
                        "id": "tavern",
                        "name": "Tavern",
                        "description": "The town tavern",
                        "sort_order": 0,
                    },
                    {
                        "id": "castle",
                        "name": "Castle",
                        "description": "The old castle",
                        "sort_order": 1,
                    },
                ],
            )
            connection.execute(
                tables["npc_profiles"].insert(),
                {
                    "id": sentinels.npc_id,
                    "name": "Grey",
                    "role": "Innkeeper",
                    "personality_json": ["patient", "observant"],
                    "sort_order": 0,
                },
            )
            connection.execute(
                tables["npc_states"].insert(),
                {
                    "npc_id": sentinels.npc_id,
                    "location_id": "tavern",
                    "current_action": "social",
                    "energy": 72,
                    "mood": 61,
                    "social": 39,
                },
            )
            connection.execute(
                tables["player_states"].insert(),
                {
                    "id": sentinels.player_id,
                    "world_id": sentinels.world_id,
                    "location_id": "castle",
                    "updated_at": created_at,
                },
            )
            connection.execute(
                tables["quest_progress"].insert(),
                {
                    "player_id": sentinels.player_id,
                    "quest_id": sentinels.quest_id,
                    "status": "accepted",
                    "version": 2,
                    "updated_tick": 44,
                    "updated_at": created_at,
                },
            )
            connection.execute(
                tables["quest_events"].insert(),
                {
                    "player_id": sentinels.player_id,
                    "quest_id": sentinels.quest_id,
                    "from_status": "locked",
                    "to_status": "accepted",
                    "interaction": "investigate",
                    "location_id": "castle",
                    "world_tick": 44,
                    "created_at": created_at,
                },
            )
            action_id = connection.execute(
                tables["actions"].insert(),
                {
                    "world_id": sentinels.world_id,
                    "tick": 43,
                    "actor_id": sentinels.npc_id,
                    "action_type": "social",
                    "target_kind": "npc",
                    "target_id": sentinels.player_id,
                    "reason": "legacy_social",
                    "status": "recorded",
                    "world_time": "15:00",
                },
            ).inserted_primary_key[0]
            connection.execute(
                tables["events"].insert(),
                {
                    "world_id": sentinels.world_id,
                    "tick": 43,
                    "event_type": "npc_action",
                    "actor_id": sentinels.npc_id,
                    "action_id": action_id,
                    "description": "Grey spoke with the player.",
                    "world_time": "15:00",
                },
            )
            connection.execute(
                tables["conversations"].insert(),
                {
                    "id": sentinels.conversation_id,
                    "world_id": sentinels.world_id,
                    "npc_id": sentinels.npc_id,
                    "created_tick": 42,
                    "created_at": created_at,
                    "updated_at": created_at,
                },
            )
            connection.execute(
                tables["conversation_messages"].insert(),
                [
                    {
                        "conversation_id": sentinels.conversation_id,
                        "role": "user",
                        "content": "Have you seen the missing child?",
                        "emotion": None,
                        "provider": None,
                        "fallback_used": 0,
                        "prompt_version": None,
                        "world_tick": 42,
                        "created_at": created_at,
                    },
                    {
                        "conversation_id": sentinels.conversation_id,
                        "role": "assistant",
                        "content": "Ask at the castle gate.",
                        "emotion": "concerned",
                        "provider": "legacy-provider",
                        "fallback_used": 1,
                        "prompt_version": "legacy-v1",
                        "world_tick": 43,
                        "created_at": created_at,
                    },
                ],
            )
    finally:
        target_engine.dispose()
        source_engine.dispose()
        source_path.unlink(missing_ok=True)

    if stamped_revision is not None:
        command.stamp(_alembic_config(database_url), stamped_revision)
    return sentinels
