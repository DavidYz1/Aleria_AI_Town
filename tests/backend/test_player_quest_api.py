from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError

from backend.app.api.dependencies import get_session
from backend.app.core.config import Settings
from backend.app.database.connection import create_engine_and_session
from backend.app.database.models import (
    PlayerState,
    QuestEvent,
    QuestProgress,
)
from backend.app.main import create_app
from scripts.seed_world import seed_database


def _app(database_url: str):
    return create_app(
        database_url,
        settings=Settings(_env_file=None, chat_provider="mock"),
    )


@pytest.mark.anyio
async def test_get_player_returns_seeded_player_and_quest_envelope(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    transport = ASGITransport(app=_app(database_url))

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/player")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": {
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
        },
        "message": "ok",
    }


@pytest.mark.anyio
async def test_travel_is_persistent_and_same_location_is_idempotent(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    transport = ASGITransport(app=_app(database_url))

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        same = await client.post(
            "/api/player/travel",
            json={"target_location_id": "tavern"},
        )
        moved = await client.post(
            "/api/player/travel",
            json={"target_location_id": "castle"},
        )

    fresh_transport = ASGITransport(app=_app(database_url))
    async with AsyncClient(
        transport=fresh_transport,
        base_url="http://test",
    ) as client:
        persisted = await client.get("/api/player")

    assert same.status_code == 200
    assert same.json()["data"]["quest"]["version"] == 0
    assert moved.status_code == 200
    assert moved.json()["data"]["player"]["location_id"] == "castle"
    assert persisted.json()["data"]["player"]["location_id"] == "castle"


@pytest.mark.anyio
async def test_missing_child_api_completes_all_five_versioned_transitions(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    transport = ASGITransport(app=_app(database_url))

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        responses = []
        responses.append(
            await client.post(
                "/api/quests/missing-child/interact",
                json={"interaction": "accept_quest", "expected_version": 0},
            )
        )
        await client.post(
            "/api/player/travel",
            json={"target_location_id": "castle"},
        )
        responses.append(
            await client.post(
                "/api/quests/missing-child/interact",
                json={"interaction": "ask_grey", "expected_version": 1},
            )
        )
        await client.post(
            "/api/player/travel",
            json={"target_location_id": "forest"},
        )
        responses.append(
            await client.post(
                "/api/quests/missing-child/interact",
                json={"interaction": "inspect_shoe", "expected_version": 2},
            )
        )
        responses.append(
            await client.post(
                "/api/quests/missing-child/interact",
                json={"interaction": "search_child", "expected_version": 3},
            )
        )
        await client.post(
            "/api/player/travel",
            json={"target_location_id": "tavern"},
        )
        responses.append(
            await client.post(
                "/api/quests/missing-child/interact",
                json={"interaction": "return_child", "expected_version": 4},
            )
        )

    assert [response.status_code for response in responses] == [
        200,
        200,
        200,
        200,
        200,
    ]
    assert [response.json()["data"]["quest"]["status"] for response in responses] == [
        "accepted",
        "briefed_by_grey",
        "shoe_found",
        "child_found",
        "completed",
    ]
    completed = responses[-1].json()["data"]
    assert completed["quest"]["version"] == 5
    assert completed["quest"]["objective"] == "任务已完成。"
    assert completed["quest"]["available_interactions"] == []
    assert len(completed["quest"]["recent_events"]) == 5

    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        assert session.scalar(
            select(func.count()).select_from(QuestEvent)
        ) == 5


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/api/player/travel", {}),
        ("/api/player/travel", {"target_location_id": "../castle"}),
        (
            "/api/quests/missing-child/interact",
            {"interaction": "unknown", "expected_version": 0},
        ),
        (
            "/api/quests/missing-child/interact",
            {"interaction": "ask_grey", "expected_version": -1},
        ),
    ],
)
async def test_player_quest_api_rejects_invalid_requests(
    database_url,
    seed_dir,
    path,
    payload,
):
    seed_database(database_url, seed_dir)
    transport = ASGITransport(app=_app(database_url))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(path, json=payload)

    assert response.status_code == 422


@pytest.mark.anyio
async def test_player_quest_api_returns_404_for_unknown_location(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    transport = ASGITransport(app=_app(database_url))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/player/travel",
            json={"target_location_id": "missing-location"},
        )

    assert response.status_code == 404
    assert response.json()["message"] == "Location not found"


@pytest.mark.anyio
async def test_player_quest_api_returns_409_for_stale_or_unavailable_interaction(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    transport = ASGITransport(app=_app(database_url))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        unavailable = await client.post(
            "/api/quests/missing-child/interact",
            json={"interaction": "ask_grey", "expected_version": 0},
        )
        accepted = await client.post(
            "/api/quests/missing-child/interact",
            json={"interaction": "accept_quest", "expected_version": 0},
        )
        stale = await client.post(
            "/api/quests/missing-child/interact",
            json={"interaction": "accept_quest", "expected_version": 0},
        )

    assert unavailable.status_code == 409
    assert unavailable.json()["message"] == (
        "Quest interaction is not available"
    )
    assert accepted.status_code == 200
    assert stale.status_code == 409
    assert stale.json()["message"] == "Quest state has changed"


@pytest.mark.anyio
async def test_player_quest_api_distinguishes_missing_player_and_quest(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        session.execute(delete(QuestProgress))
        session.commit()

    transport = ASGITransport(app=_app(database_url))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        missing_quest = await client.get("/api/player")

    with session_factory() as session:
        session.execute(delete(PlayerState))
        session.commit()

    transport = ASGITransport(app=_app(database_url))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        missing_player = await client.get("/api/player")

    assert missing_quest.status_code == 404
    assert missing_quest.json()["message"] == "Quest not found"
    assert missing_player.status_code == 404
    assert missing_player.json()["message"] == "Player not found"


@pytest.mark.anyio
async def test_player_quest_api_returns_safe_503_for_uninitialized_database(
    database_url,
):
    transport = ASGITransport(
        app=_app(database_url),
        raise_app_exceptions=False,
    )
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/player")

    assert response.status_code == 503
    assert response.json() == {
        "success": False,
        "data": None,
        "message": "Player quest service is unavailable",
    }


@pytest.mark.anyio
async def test_player_travel_returns_503_and_rolls_back_when_commit_fails(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    app = _app(database_url)
    _, session_factory = create_engine_and_session(database_url)

    def failing_session():
        with session_factory() as session:
            def fail_commit():
                raise SQLAlchemyError("forced commit failure")

            session.commit = fail_commit
            yield session

    app.dependency_overrides[get_session] = failing_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/player/travel",
            json={"target_location_id": "castle"},
        )

    with session_factory() as session:
        player = session.get(PlayerState, "default-player")

    assert response.status_code == 503
    assert response.json()["message"] == (
        "Player quest service is unavailable"
    )
    assert player is not None
    assert player.location_id == "tavern"
