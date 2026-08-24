import sqlite3

import pytest

from backend.app.database.connection import create_engine_and_session
from backend.app.database.models import NpcState, WorldAction
from backend.app.database.npc_repository import (
    NpcDetailUnavailableError,
    NpcNotFoundError,
    NpcRepository,
)
from backend.app.database.world_tick_repository import WorldTickRepository
from backend.app.world.tick_engine import run_tick
from scripts.seed_world import seed_database


def test_repository_returns_authoritative_npc_detail_without_history(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)

    with session_factory() as session:
        records = NpcRepository(session).get_detail_records("ryan")

    assert records.profile.id == "ryan"
    assert records.profile.name == "Ryan"
    assert records.state.location_id == "park"
    assert records.location.name == "中央公园"
    assert (records.world.day, records.world.time, records.world.tick) == (
        1,
        "08:00",
        0,
    )
    assert records.actions == ()
    assert records.target_names == {}


def test_repository_returns_only_three_most_recent_actions_in_stable_order(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)

    with session_factory() as session:
        tick_repository = WorldTickRepository(session)
        for expected_tick in range(4):
            tick_repository.persist_tick(
                expected_tick,
                run_tick(tick_repository.get_snapshot()),
            )

        records = NpcRepository(session).get_detail_records("ryan")

    assert [action.tick for action in records.actions] == [4, 3, 2]
    assert [
        (
            action.world_time,
            action.action_type,
            action.target_kind,
            action.target_id,
            action.reason,
        )
        for action in records.actions
    ] == [
        ("12:00", "work", None, None, "knight_training"),
        ("11:00", "work", None, None, "knight_training"),
        ("10:00", "work", None, None, "knight_training"),
    ]
    assert all(action.id > 0 for action in records.actions)


def test_repository_resolves_action_targets_in_batches_and_keeps_unknown_targets(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)

    with session_factory() as session:
        session.add_all(
            [
                WorldAction(
                    world_id="aleria-town",
                    tick=1,
                    actor_id="ryan",
                    action_type="move",
                    target_kind="location",
                    target_id="park",
                    reason="knight_duty_travel",
                    status="recorded",
                    world_time="09:00",
                ),
                WorldAction(
                    world_id="aleria-town",
                    tick=2,
                    actor_id="ryan",
                    action_type="social",
                    target_kind="npc",
                    target_id="grey",
                    reason="knight_evening_social",
                    status="recorded",
                    world_time="10:00",
                ),
                WorldAction(
                    world_id="aleria-town",
                    tick=3,
                    actor_id="ryan",
                    action_type="move",
                    target_kind="location",
                    target_id="missing-place",
                    reason="knight_duty_travel",
                    status="recorded",
                    world_time="11:00",
                ),
            ]
        )
        session.commit()

        records = NpcRepository(session).get_detail_records("ryan")

    assert records.target_names[("location", "park")] == "中央公园"
    assert records.target_names[("npc", "grey")] == "Grey"
    assert ("location", "missing-place") not in records.target_names
    assert [action.target_id for action in records.actions] == [
        "missing-place",
        "grey",
        "park",
    ]


def test_repository_reports_unknown_profile_as_not_found(database_url, seed_dir):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)

    with session_factory() as session:
        with pytest.raises(NpcNotFoundError, match="^NPC not found$"):
            NpcRepository(session).get_detail_records("missing-npc")


def test_repository_reports_missing_state_as_unavailable(database_url, seed_dir):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)

    with session_factory() as session:
        state = session.get(NpcState, "ryan")
        assert state is not None
        session.delete(state)
        session.commit()

        with pytest.raises(
            NpcDetailUnavailableError,
            match="^NPC detail is unavailable$",
        ):
            NpcRepository(session).get_detail_records("ryan")


def test_repository_reports_missing_world_as_unavailable(database_url, seed_dir):
    seed_database(database_url, seed_dir)
    database_path = database_url.removeprefix("sqlite:///")
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute(
            "DELETE FROM world_state WHERE id = ?",
            ("aleria-town",),
        )

    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        with pytest.raises(
            NpcDetailUnavailableError,
            match="^NPC detail is unavailable$",
        ):
            NpcRepository(session).get_detail_records("ryan")


def test_repository_reports_missing_current_location_as_unavailable(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    database_path = database_url.removeprefix("sqlite:///")
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("DELETE FROM locations WHERE id = ?", ("park",))

    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        with pytest.raises(
            NpcDetailUnavailableError,
            match="^NPC detail is unavailable$",
        ):
            NpcRepository(session).get_detail_records("ryan")
