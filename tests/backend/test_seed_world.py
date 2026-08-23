from datetime import UTC, datetime
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from backend.app.database.connection import create_engine_and_session
from backend.app.database.models import (
    Conversation,
    ConversationMessage,
    Event,
    Location,
    NpcProfile,
    NpcState,
    WorldAction,
    WorldState,
)
from backend.app.database.world_tick_repository import WorldTickRepository
from backend.app.world.tick_engine import run_tick
from scripts.seed_world import load_seed_data, seed_database


REPO_ROOT = Path(__file__).resolve().parents[2]


def _add_chat_turn(session, conversation_id: str, world_id: str) -> None:
    now = datetime.now(UTC)
    session.add(
        Conversation(
            id=conversation_id,
            world_id=world_id,
            npc_id="ryan",
            created_tick=0,
            created_at=now,
            updated_at=now,
        )
    )
    session.add_all(
        [
            ConversationMessage(
                conversation_id=conversation_id,
                role="user",
                content="你好",
                emotion=None,
                provider=None,
                fallback_used=0,
                prompt_version=None,
                world_tick=0,
                created_at=now,
            ),
            ConversationMessage(
                conversation_id=conversation_id,
                role="assistant",
                content="你好，旅行者。",
                emotion="cheerful",
                provider="mock",
                fallback_used=0,
                prompt_version="v1",
                world_tick=0,
                created_at=now,
            ),
        ]
    )


def test_seed_database_is_idempotent(database_url, seed_dir):
    seed_database(database_url, seed_dir)

    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        world = session.get(WorldState, "aleria-town")
        ryan = session.get(NpcState, "ryan")
        assert world is not None
        assert ryan is not None
        world.day = 9
        ryan.energy = 1
        session.commit()

    seed_database(database_url, seed_dir)

    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(WorldState)) == 1
        assert session.scalar(select(func.count()).select_from(Location)) == 2
        assert session.scalar(select(func.count()).select_from(NpcProfile)) == 3
        assert session.scalar(select(func.count()).select_from(NpcState)) == 3
        world = session.get(WorldState, "aleria-town")
        ryan = session.get(NpcState, "ryan")

    assert world is not None
    assert (world.name, world.day, world.time, world.tick) == ("晨曦镇", 1, "08:00", 0)
    assert ryan is not None
    assert (ryan.location_id, ryan.energy, ryan.mood, ryan.social) == (
        "park",
        80,
        78,
        70,
    )


def test_reseed_resets_tick_history_consistently(database_url, seed_dir):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        repository = WorldTickRepository(session)
        repository.persist_tick(0, run_tick(repository.get_snapshot()))

    seed_database(database_url, seed_dir)

    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(WorldAction)) == 0
        assert session.scalar(select(func.count()).select_from(Event)) == 0
        repository = WorldTickRepository(session)
        assert repository.get_snapshot().tick == 0
        persisted = repository.persist_tick(0, run_tick(repository.get_snapshot()))
        assert persisted.result.world.tick == 1


def test_reseed_removes_chat_history_before_resetting_canonical_world(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        repository = WorldTickRepository(session)
        repository.persist_tick(0, run_tick(repository.get_snapshot()))
        _add_chat_turn(session, "canonical-conversation", "aleria-town")
        session.commit()

    seed_database(database_url, seed_dir)

    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Conversation)) == 0
        assert (
            session.scalar(
                select(func.count()).select_from(ConversationMessage)
            )
            == 0
        )
        assert session.scalar(select(func.count()).select_from(WorldAction)) == 0
        assert session.scalar(select(func.count()).select_from(Event)) == 0
        world = session.get(WorldState, "aleria-town")

    assert world is not None
    assert (world.day, world.time, world.tick) == (1, "08:00", 0)


def test_reseed_preserves_chat_history_for_other_worlds(database_url, seed_dir):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        session.add(
            WorldState(
                id="other-world",
                name="远方小镇",
                day=2,
                time="10:00",
                tick=5,
            )
        )
        session.flush()
        _add_chat_turn(session, "other-conversation", "other-world")
        session.commit()

    seed_database(database_url, seed_dir)

    with session_factory() as session:
        conversations = tuple(session.scalars(select(Conversation)))
        messages = tuple(session.scalars(select(ConversationMessage)))

    assert [conversation.id for conversation in conversations] == [
        "other-conversation"
    ]
    assert [message.conversation_id for message in messages] == [
        "other-conversation",
        "other-conversation",
    ]


def test_seed_data_rejects_need_outside_zero_to_one_hundred(tmp_path, seed_dir):
    invalid_seed_dir = tmp_path / "data"
    shutil.copytree(seed_dir, invalid_seed_dir)
    npcs_path = invalid_seed_dir / "npcs.json"
    npcs = json.loads(npcs_path.read_text(encoding="utf-8"))
    npcs[0]["state"]["energy"] = 101
    npcs_path.write_text(
        json.dumps(npcs, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        load_seed_data(invalid_seed_dir)


def test_seed_data_rejects_unknown_npc_location(tmp_path, seed_dir):
    invalid_seed_dir = tmp_path / "data"
    shutil.copytree(seed_dir, invalid_seed_dir)
    npcs_path = invalid_seed_dir / "npcs.json"
    npcs = json.loads(npcs_path.read_text(encoding="utf-8"))
    npcs[0]["state"]["location_id"] = "missing-place"
    npcs_path.write_text(json.dumps(npcs, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValidationError, match="unknown location_id 'missing-place'"):
        load_seed_data(invalid_seed_dir)


def test_seed_data_rejects_duplicate_ids_and_sort_orders(tmp_path, seed_dir):
    invalid_seed_dir = tmp_path / "data"
    shutil.copytree(seed_dir, invalid_seed_dir)
    locations_path = invalid_seed_dir / "locations.json"
    locations = json.loads(locations_path.read_text(encoding="utf-8"))
    locations[1]["id"] = locations[0]["id"]
    locations[1]["sort_order"] = locations[0]["sort_order"]
    locations_path.write_text(
        json.dumps(locations, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError) as exc_info:
        load_seed_data(invalid_seed_dir)

    message = str(exc_info.value)
    assert "duplicate location id 'tavern'" in message
    assert "duplicate location sort_order '1'" in message


def test_seed_script_can_be_executed_directly(database_url):
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "seed_world.py")],
        cwd=REPO_ROOT,
        env={**os.environ, "DATABASE_URL": database_url},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Seeded Aleria world into SQLite." in result.stdout
