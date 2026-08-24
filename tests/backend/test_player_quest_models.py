from datetime import UTC, datetime

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from backend.app.database import models
from backend.app.database.connection import create_engine_and_session
from scripts.seed_world import seed_database
from scripts.upgrade_schema import upgrade_schema


def _model(name: str):
    model = getattr(models, name, None)
    assert model is not None, f"{name} model is missing"
    return model


def _add_player_and_progress(session):
    PlayerState = _model("PlayerState")
    QuestProgress = _model("QuestProgress")
    assert session.get(PlayerState, "default-player") is not None
    assert (
        session.get(
            QuestProgress,
            ("default-player", "missing-child"),
        )
        is not None
    )


def test_upgrade_schema_creates_player_quest_tables_and_event_index(database_url):
    upgrade_schema(database_url)
    engine, _ = create_engine_and_session(database_url)
    inspector = inspect(engine)

    assert {"player_states", "quest_progress", "quest_events"} <= set(
        inspector.get_table_names()
    )
    assert "ix_quest_events_player_quest_id" in {
        item["name"] for item in inspector.get_indexes("quest_events")
    }


@pytest.mark.parametrize(
    ("model_name", "invalid_field"),
    [
        ("QuestProgress", "version"),
        ("QuestProgress", "updated_tick"),
        ("QuestEvent", "world_tick"),
    ],
)
def test_player_quest_models_reject_negative_counters(
    database_url,
    seed_dir,
    model_name,
    invalid_field,
):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        _add_player_and_progress(session)
        if model_name == "QuestProgress":
            progress = session.get(
                _model("QuestProgress"),
                ("default-player", "missing-child"),
            )
            setattr(progress, invalid_field, -1)
        else:
            session.add(
                _model("QuestEvent")(
                    player_id="default-player",
                    quest_id="missing-child",
                    from_status="available",
                    to_status="accepted",
                    interaction="accept_quest",
                    location_id="tavern",
                    world_tick=-1,
                )
            )

        with pytest.raises(IntegrityError):
            session.commit()


@pytest.mark.parametrize(
    "invalid_row",
    [
        {
            "model": "PlayerState",
            "values": {
                "id": "orphan-player",
                "world_id": "missing-world",
                "location_id": "tavern",
            },
        },
        {
            "model": "PlayerState",
            "values": {
                "id": "orphan-player",
                "world_id": "aleria-town",
                "location_id": "missing-location",
            },
        },
        {
            "model": "QuestProgress",
            "values": {
                "player_id": "missing-player",
                "quest_id": "missing-child",
                "status": "available",
                "version": 0,
                "updated_tick": 0,
            },
        },
        {
            "model": "QuestEvent",
            "values": {
                "player_id": "missing-player",
                "quest_id": "missing-child",
                "from_status": "available",
                "to_status": "accepted",
                "interaction": "accept_quest",
                "location_id": "missing-location",
                "world_tick": 0,
                "created_at": datetime.now(UTC),
            },
        },
    ],
)
def test_player_quest_models_enforce_foreign_keys(
    database_url,
    seed_dir,
    invalid_row,
):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        model = _model(invalid_row["model"])
        session.add(model(**invalid_row["values"]))

        with pytest.raises(IntegrityError):
            session.commit()


def test_quest_progress_rejects_duplicate_player_quest_key(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        _add_player_and_progress(session)
        session.add(
            _model("QuestProgress")(
                player_id="default-player",
                quest_id="missing-child",
                status="accepted",
                version=1,
                updated_tick=0,
            )
        )

        with pytest.raises(IntegrityError):
            session.commit()
