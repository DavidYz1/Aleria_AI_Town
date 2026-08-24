import importlib

import pytest
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import SQLAlchemyError

from backend.app.database.connection import create_engine_and_session
from backend.app.database.models import NpcState, QuestEvent, QuestProgress
from backend.app.quests.missing_child import MissingChildQuestPolicy
from backend.app.quests.types import QuestCommand, QuestSnapshot
from scripts.seed_world import seed_database


def _repository_module():
    try:
        return importlib.import_module(
            "backend.app.database.player_quest_repository"
        )
    except ModuleNotFoundError:
        pytest.fail("player quest repository is missing")


def _available_transition():
    return MissingChildQuestPolicy().transition(
        QuestSnapshot(
            quest_id="missing-child",
            status="available",
            version=0,
            player_location_id="tavern",
            world_tick=0,
        ),
        QuestCommand(interaction="accept_quest", expected_version=0),
    )


def test_repository_reads_authoritative_state_and_latest_five_events(
    database_url,
    seed_dir,
):
    repository_module = _repository_module()
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        session.add_all(
            [
                QuestEvent(
                    player_id="default-player",
                    quest_id="missing-child",
                    from_status="available",
                    to_status="accepted",
                    interaction="accept_quest",
                    location_id="tavern",
                    world_tick=index,
                )
                for index in range(6)
            ]
        )
        session.commit()

        records = repository_module.PlayerQuestRepository(session).get_state(
            "default-player",
            "missing-child",
        )

    assert (
        records.player_id,
        records.world_id,
        records.location_id,
        records.location_name,
    ) == ("default-player", "aleria-town", "tavern", "星辉酒馆")
    assert (
        records.quest_id,
        records.status,
        records.version,
        records.updated_tick,
        records.world_tick,
    ) == ("missing-child", "available", 0, 0, 0)
    assert (
        records.target_npc_location_id,
        records.target_npc_location_name,
    ) == ("castle", "晨曦城堡")
    assert [event.id for event in records.recent_events] == [2, 3, 4, 5, 6]


def test_repository_travel_persists_and_same_location_is_idempotent(
    database_url,
    seed_dir,
):
    repository_module = _repository_module()
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        repository = repository_module.PlayerQuestRepository(session)
        travelled = repository.travel(
            "default-player",
            "missing-child",
            "castle",
        )
        repeated = repository.travel(
            "default-player",
            "missing-child",
            "castle",
        )

    with session_factory() as session:
        persisted = repository_module.PlayerQuestRepository(session).get_state(
            "default-player",
            "missing-child",
        )
        event_count = session.scalar(
            select(func.count()).select_from(QuestEvent)
        )

    assert travelled.location_id == "castle"
    assert repeated.location_id == "castle"
    assert persisted.location_id == "castle"
    assert persisted.version == 0
    assert event_count == 0


def test_repository_travel_rejects_unknown_location(database_url, seed_dir):
    repository_module = _repository_module()
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        with pytest.raises(
            repository_module.LocationNotFoundError,
            match="^Location not found$",
        ):
            repository_module.PlayerQuestRepository(session).travel(
                "default-player",
                "missing-child",
                "missing-location",
            )


def test_repository_applies_versioned_transition_and_inserts_event_atomically(
    database_url,
    seed_dir,
):
    repository_module = _repository_module()
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        records = repository_module.PlayerQuestRepository(
            session
        ).apply_transition(
            player_id="default-player",
            quest_id="missing-child",
            expected_version=0,
            transition=_available_transition(),
        )

    with session_factory() as session:
        progress = session.get(
            QuestProgress,
            ("default-player", "missing-child"),
        )
        events = tuple(session.scalars(select(QuestEvent)))

    assert records.status == "accepted"
    assert records.version == 1
    assert progress is not None
    assert (progress.status, progress.version, progress.updated_tick) == (
        "accepted",
        1,
        0,
    )
    assert len(events) == 1
    assert (
        events[0].from_status,
        events[0].to_status,
        events[0].interaction,
        events[0].location_id,
        events[0].world_tick,
    ) == (
        "available",
        "accepted",
        "accept_quest",
        "tavern",
        0,
    )


def test_repository_rejects_stale_version_without_extra_event(
    database_url,
    seed_dir,
):
    repository_module = _repository_module()
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        repository = repository_module.PlayerQuestRepository(session)
        repository.apply_transition(
            player_id="default-player",
            quest_id="missing-child",
            expected_version=0,
            transition=_available_transition(),
        )
        with pytest.raises(
            repository_module.QuestStateConflictError,
            match="^Quest state has changed$",
        ):
            repository.apply_transition(
                player_id="default-player",
                quest_id="missing-child",
                expected_version=0,
                transition=_available_transition(),
            )

    with session_factory() as session:
        assert (
            session.scalar(select(func.count()).select_from(QuestEvent))
            == 1
        )


def test_repository_rechecks_player_location_before_transition(
    database_url,
    seed_dir,
):
    repository_module = _repository_module()
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        repository = repository_module.PlayerQuestRepository(session)
        repository.travel(
            "default-player",
            "missing-child",
            "castle",
        )
        with pytest.raises(
            repository_module.QuestInteractionUnavailableError,
            match="^Quest interaction is not available$",
        ):
            repository.apply_transition(
                player_id="default-player",
                quest_id="missing-child",
                expected_version=0,
                transition=_available_transition(),
            )


def test_repository_rechecks_required_npc_location_before_transition(
    database_url,
    seed_dir,
):
    repository_module = _repository_module()
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        repository = repository_module.PlayerQuestRepository(session)
        repository.apply_transition(
            player_id="default-player",
            quest_id="missing-child",
            expected_version=0,
            transition=_available_transition(),
        )
        repository.travel(
            "default-player",
            "missing-child",
            "castle",
        )
        records = repository.get_state("default-player", "missing-child")
        transition = MissingChildQuestPolicy().transition(
            QuestSnapshot(
                quest_id=records.quest_id,
                status="accepted",
                version=records.version,
                player_location_id=records.location_id,
                world_tick=records.world_tick,
                target_npc_location_id=records.target_npc_location_id,
            ),
            QuestCommand(interaction="ask_grey", expected_version=1),
        )

        session.execute(
            update(NpcState)
            .where(NpcState.npc_id == "grey")
            .values(location_id="park")
            .execution_options(synchronize_session=False)
        )

        with pytest.raises(
            repository_module.QuestInteractionUnavailableError,
            match="^Quest interaction is not available$",
        ):
            repository.apply_transition(
                player_id="default-player",
                quest_id="missing-child",
                expected_version=1,
                transition=transition,
            )

    with session_factory() as session:
        progress = session.get(
            QuestProgress,
            ("default-player", "missing-child"),
        )
        event_count = session.scalar(
            select(func.count()).select_from(QuestEvent)
        )

    assert progress is not None
    assert (progress.status, progress.version) == ("accepted", 1)
    assert event_count == 1


def test_repository_rolls_back_progress_and_event_when_commit_fails(
    database_url,
    seed_dir,
):
    repository_module = _repository_module()
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        repository = repository_module.PlayerQuestRepository(session)

        def fail_commit():
            raise SQLAlchemyError("forced commit failure")

        session.commit = fail_commit
        with pytest.raises(
            repository_module.PlayerQuestPersistenceError,
            match="^Player quest service is unavailable$",
        ):
            repository.apply_transition(
                player_id="default-player",
                quest_id="missing-child",
                expected_version=0,
                transition=_available_transition(),
            )

    with session_factory() as session:
        progress = session.get(
            QuestProgress,
            ("default-player", "missing-child"),
        )
        event_count = session.scalar(
            select(func.count()).select_from(QuestEvent)
        )

    assert progress is not None
    assert (progress.status, progress.version) == ("available", 0)
    assert event_count == 0


def test_repository_distinguishes_missing_player_and_quest(
    database_url,
    seed_dir,
):
    repository_module = _repository_module()
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        repository = repository_module.PlayerQuestRepository(session)
        with pytest.raises(
            repository_module.PlayerNotFoundError,
            match="^Player not found$",
        ):
            repository.get_state("missing-player", "missing-child")

        session.execute(
            delete(QuestProgress).where(
                QuestProgress.player_id == "default-player",
                QuestProgress.quest_id == "missing-child",
            )
        )
        session.commit()
        with pytest.raises(
            repository_module.QuestNotFoundError,
            match="^Quest not found$",
        ):
            repository.get_state("default-player", "missing-child")
