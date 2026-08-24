import importlib

import pytest
from pydantic import ValidationError

from backend.app.database.connection import create_engine_and_session
from backend.app.database.player_quest_repository import PlayerQuestRepository
from backend.app.quests.missing_child import MissingChildQuestPolicy
from scripts.seed_world import seed_database


def _service_modules():
    try:
        player_schema = importlib.import_module("backend.app.schemas.player")
        quest_schema = importlib.import_module("backend.app.schemas.quest")
        service_module = importlib.import_module(
            "backend.app.services.player_quest_service"
        )
    except ModuleNotFoundError:
        pytest.fail("player quest schemas or service are missing")
    return player_schema, quest_schema, service_module


@pytest.mark.parametrize(
    "target_location_id",
    ["", "Castle", "../castle", "castle_room", "castle/keep"],
)
def test_player_travel_request_rejects_malformed_location_ids(
    target_location_id,
):
    player_schema, _, _ = _service_modules()

    with pytest.raises(ValidationError):
        player_schema.PlayerTravelRequest(
            target_location_id=target_location_id
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"interaction": "unknown", "expected_version": 0},
        {"interaction": "ask_grey", "expected_version": -1},
        {
            "interaction": "ask_grey",
            "expected_version": 0,
            "status": "accepted",
        },
    ],
)
def test_quest_interact_request_rejects_unknown_negative_or_extra_state(payload):
    _, quest_schema, _ = _service_modules()

    with pytest.raises(ValidationError):
        quest_schema.QuestInteractRequest(**payload)


def test_service_derives_initial_player_quest_presentation_from_backend_state(
    database_url,
    seed_dir,
):
    _, _, service_module = _service_modules()
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        data = service_module.PlayerQuestService(
            PlayerQuestRepository(session),
            MissingChildQuestPolicy(),
        ).get_state()

    assert data.model_dump() == {
        "player": {
            "id": "default-player",
            "location_id": "tavern",
            "location_name": "星辉酒馆",
        },
        "quest": {
            "id": "missing-child",
            "title": "失踪的孩子",
            "status": "available",
            "version": 0,
            "objective": "查看星辉酒馆的委托板。",
            "available_interactions": [
                {"id": "accept_quest", "label": "接受委托"}
            ],
            "recent_events": [],
        },
    }


def test_service_travel_and_interact_return_fresh_authoritative_state(
    database_url,
    seed_dir,
):
    player_schema, quest_schema, service_module = _service_modules()
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        service = service_module.PlayerQuestService(
            PlayerQuestRepository(session),
            MissingChildQuestPolicy(),
        )
        accepted = service.interact(
            quest_schema.QuestInteractRequest(
                interaction="accept_quest",
                expected_version=0,
            )
        )
        at_castle = service.travel(
            player_schema.PlayerTravelRequest(
                target_location_id="castle"
            )
        )

    assert accepted.quest.status == "accepted"
    assert accepted.quest.version == 1
    assert accepted.quest.objective == "前往晨曦城堡询问 Grey。"
    assert accepted.quest.available_interactions == []
    assert accepted.quest.recent_events[0].description == (
        "你在星辉酒馆接受了寻找失踪孩子的委托。"
    )
    assert at_castle.player.location_id == "castle"
    assert at_castle.player.location_name == "晨曦城堡"
    assert at_castle.quest.status == "accepted"
    assert at_castle.quest.version == 1
    assert [item.id for item in at_castle.quest.available_interactions] == [
        "ask_grey"
    ]
