import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.database.connection import create_engine_and_session
from backend.app.database.models import Base, WorldState
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
        "name": "晨曦镇",
        "day": 1,
        "time": "08:00",
        "tick": 0,
    }
    assert [item["id"] for item in body["data"]["locations"]] == [
        "tavern",
        "park",
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
    engine, session_factory = create_engine_and_session(database_url)
    Base.metadata.create_all(engine)
    with session_factory() as session:
        session.add(
            WorldState(
                id="other-world",
                name="错误世界",
                day=9,
                time="23:59",
                tick=99,
            )
        )
        session.commit()
    seed_database(database_url, seed_dir)

    transport = ASGITransport(app=create_app(database_url))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/world")

    assert response.status_code == 200
    assert response.json()["data"]["world"]["id"] == "aleria-town"
