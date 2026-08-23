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
