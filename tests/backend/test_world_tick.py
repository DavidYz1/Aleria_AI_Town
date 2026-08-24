from dataclasses import replace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, inspect, select

from backend.app.database.connection import create_engine_and_session
from backend.app.database.models import (
    Base,
    Event,
    Location,
    NpcProfile,
    NpcState,
    WorldAction,
    WorldState,
)
from backend.app.database.world_tick_repository import (
    WorldTickPersistenceError,
    WorldTickRepository,
)
from backend.app.main import create_app
from backend.app.world.tick_engine import run_tick
from scripts.seed_world import seed_database
from scripts.upgrade_schema import upgrade_schema


@pytest.mark.anyio
async def test_tick_advances_world_and_records_three_actions_and_events(
    database_url, seed_dir
):
    seed_database(database_url, seed_dir)
    transport = ASGITransport(app=create_app(database_url))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/world/tick", json={"expected_tick": 0})

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["world"]["world"] == {
        "id": "aleria-town",
        "name": "曦谷",
        "day": 1,
        "time": "09:00",
        "tick": 1,
    }
    assert [
        (action["actor_id"], action["action_type"], action["target_id"])
        for action in body["data"]["actions"]
    ] == [
        ("ryan", "work", None),
        ("shir", "move", "park"),
        ("grey", "work", None),
    ]
    assert len(body["data"]["events"]) == 3
    assert all(event["action_id"] for event in body["data"]["events"])

    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(WorldAction)) == 3
        assert session.scalar(select(func.count()).select_from(Event)) == 3
        shir = session.get(NpcState, "shir")
        assert shir is not None
        assert (shir.location_id, shir.current_action, shir.energy) == (
            "park",
            "move",
            65,
        )


@pytest.mark.anyio
async def test_stale_expected_tick_returns_409_without_duplicate_history(
    database_url, seed_dir
):
    seed_database(database_url, seed_dir)
    transport = ASGITransport(app=create_app(database_url))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post("/api/world/tick", json={"expected_tick": 0})
        stale = await client.post("/api/world/tick", json={"expected_tick": 0})

    assert first.status_code == 200
    assert stale.status_code == 409
    assert stale.json() == {
        "success": False,
        "data": None,
        "message": "world tick conflict; refresh and retry",
    }

    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        world = session.get(WorldState, "aleria-town")
        assert world is not None and world.tick == 1
        assert session.scalar(select(func.count()).select_from(WorldAction)) == 3
        assert session.scalar(select(func.count()).select_from(Event)) == 3


def test_repository_rolls_back_clock_state_and_history_on_invalid_result(
    database_url, seed_dir
):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        repository = WorldTickRepository(session)
        result = run_tick(repository.get_snapshot())
        broken_npc = replace(result.world.npcs[0], location_id="missing-place")
        broken_result = replace(
            result,
            world=replace(
                result.world,
                npcs=(broken_npc, *result.world.npcs[1:]),
            ),
        )

        with pytest.raises(WorldTickPersistenceError):
            repository.persist_tick(0, broken_result)

    with session_factory() as session:
        world = session.get(WorldState, "aleria-town")
        ryan = session.get(NpcState, "ryan")
        assert world is not None and (world.time, world.tick) == ("08:00", 0)
        assert ryan is not None and ryan.location_id == "park"
        assert session.scalar(select(func.count()).select_from(WorldAction)) == 0
        assert session.scalar(select(func.count()).select_from(Event)) == 0


@pytest.mark.anyio
async def test_tick_returns_503_when_database_is_uninitialized(database_url):
    transport = ASGITransport(app=create_app(database_url), raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/world/tick", json={"expected_tick": 0})

    assert response.status_code == 503
    assert response.json()["message"] == "world state is unavailable"


@pytest.mark.anyio
async def test_tick_rejects_partially_initialized_canonical_world(database_url):
    engine, session_factory = create_engine_and_session(database_url)
    Base.metadata.create_all(engine)
    with session_factory() as session:
        session.add(
            WorldState(
                id="aleria-town",
                name="晨曦镇",
                day=1,
                time="08:00",
                tick=0,
            )
        )
        session.commit()

    transport = ASGITransport(app=create_app(database_url))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/world/tick", json={"expected_tick": 0})

    assert response.status_code == 503
    with session_factory() as session:
        world = session.get(WorldState, "aleria-town")
        assert world is not None and world.tick == 0


def test_schema_upgrade_adds_phase_1a_tables_without_resetting_phase_0_state(
    database_url,
):
    engine, session_factory = create_engine_and_session(database_url)
    for table in (
        WorldState.__table__,
        Location.__table__,
        NpcProfile.__table__,
        NpcState.__table__,
    ):
        table.create(engine)
    with session_factory() as session:
        session.add(
            WorldState(
                id="aleria-town",
                name="晨曦镇",
                day=7,
                time="16:00",
                tick=44,
            )
        )
        session.commit()

    upgrade_schema(database_url)

    assert {"actions", "events"}.issubset(inspect(engine).get_table_names())
    with session_factory() as session:
        world = session.get(WorldState, "aleria-town")
        assert world is not None
        assert (world.day, world.time, world.tick) == (7, "16:00", 44)


@pytest.mark.anyio
async def test_tick_rejects_negative_expected_tick(database_url, seed_dir):
    seed_database(database_url, seed_dir)
    transport = ASGITransport(app=create_app(database_url))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/world/tick", json={"expected_tick": -1})

    assert response.status_code == 422


@pytest.mark.anyio
async def test_post_tick_allows_documented_frontend_origin(database_url, seed_dir):
    seed_database(database_url, seed_dir)
    transport = ASGITransport(app=create_app(database_url))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/api/world/tick",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert response.status_code == 200
    assert "POST" in response.headers["access-control-allow-methods"]


@pytest.mark.anyio
async def test_get_world_matches_world_returned_by_latest_tick(database_url, seed_dir):
    seed_database(database_url, seed_dir)
    transport = ASGITransport(app=create_app(database_url))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        tick = await client.post("/api/world/tick", json={"expected_tick": 0})
        current = await client.get("/api/world")

    assert tick.status_code == current.status_code == 200
    assert tick.json()["data"]["world"] == current.json()["data"]
