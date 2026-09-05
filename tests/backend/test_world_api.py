import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.database.connection import create_engine_and_session
from backend.app.database.models import Base, NpcState, WorldState
from backend.app.main import create_app
from scripts.seed_world import seed_database


@pytest.mark.anyio
async def test_get_world_returns_canonical_seeded_world(database_url, seed_dir):
    seed_database(database_url, seed_dir)
    transport = ASGITransport(app=create_app(database_url))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/world")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "ok"
    assert body["data"]["world"] == {
        "id": "aleria-town",
        "name": "曦谷",
        "day": 1,
        "time": "08:00",
        "world_version": 0,
        "clock_tick": 0,
        "event_sequence": 0,
    }
    assert [
        (item["id"], item["name"])
        for item in body["data"]["locations"]
    ] == [
        ("tavern", "星辉酒馆"),
        ("park", "中央公园"),
        ("castle", "晨曦城堡"),
        ("forest", "低语森林"),
    ]
    assert [item["id"] for item in body["data"]["npcs"]] == [
        "ryan",
        "shir",
        "grey",
    ]
    assert body["data"]["npcs"][0]["status"] == {
        "energy": 80,
        "mood": 78,
        "social": 70,
    }


@pytest.mark.anyio
async def test_get_world_returns_safe_503_when_database_is_uninitialized(database_url):
    transport = ASGITransport(app=create_app(database_url), raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/world")

    assert response.status_code == 503
    assert response.json() == {
        "success": False,
        "data": None,
        "message": "world state is unavailable",
    }


@pytest.mark.anyio
async def test_get_world_exposes_legacy_social_state_as_talk(database_url, seed_dir):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        state = session.get(NpcState, "ryan")
        assert state is not None
        state.current_action = "social"
        session.commit()

    transport = ASGITransport(app=create_app(database_url))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/world")

    assert response.status_code == 200
    assert response.json()["data"]["npcs"][0]["current_action"] == "talk"


@pytest.mark.anyio
async def test_get_world_allows_documented_frontend_origin(database_url, seed_dir):
    seed_database(database_url, seed_dir)
    transport = ASGITransport(app=create_app(database_url))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/world",
            headers={"Origin": "http://127.0.0.1:5173"},
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


@pytest.mark.anyio
async def test_get_world_selects_canonical_world_when_an_extra_row_exists(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        session.add(
            WorldState(
                id="other-world",
                name="错误世界",
                day=9,
                time="23:59",
                clock_tick=99,
                world_version=99,
                event_sequence=0,
            )
        )
        session.commit()
    transport = ASGITransport(app=create_app(database_url))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/world")

    assert response.status_code == 200
    assert response.json()["data"]["world"]["id"] == "aleria-town"
