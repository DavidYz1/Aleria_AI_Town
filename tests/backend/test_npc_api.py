import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.database.connection import create_engine_and_session
from backend.app.database.models import NpcState
from backend.app.main import create_app
from scripts.seed_world import seed_database


@pytest.mark.anyio
async def test_get_npc_detail_returns_complete_public_contract_after_tick(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    transport = ASGITransport(app=create_app(database_url))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        tick_response = await client.post(
            "/api/world/tick",
            json={"expected_tick": 0},
        )
        response = await client.get("/api/npcs/ryan")

    assert tick_response.status_code == 200
    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": {
            "profile": {
                "id": "ryan",
                "name": "Ryan",
                "role": "Knight",
                "personality": ["optimistic", "brave", "kind"],
            },
            "state": {
                "location_id": "park",
                "location_name": "中央公园",
                "current_action": "work",
                "status": {
                    "energy": 70,
                    "mood": 75,
                    "social": 67,
                },
            },
            "world_context": {
                "day": 1,
                "time": "09:00",
                "tick": 1,
                "time_phase": "morning",
            },
            "recent_actions": [
                {
                    "id": 1,
                    "tick": 1,
                    "world_time": "09:00",
                    "action_type": "work",
                    "target_kind": None,
                    "target_id": None,
                    "target_name": None,
                    "reason_code": "knight_duty",
                    "reason_text": "当前处于骑士履行训练职责的时间。",
                }
            ],
        },
        "message": "ok",
    }


@pytest.mark.anyio
async def test_get_npc_detail_returns_empty_history_before_first_tick(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    transport = ASGITransport(app=create_app(database_url))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/npcs/shir")

    assert response.status_code == 200
    assert response.json()["data"]["state"]["current_action"] == "eat"
    assert response.json()["data"]["recent_actions"] == []


@pytest.mark.anyio
async def test_get_npc_detail_limits_history_to_three_newest_actions(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    transport = ASGITransport(app=create_app(database_url))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for expected_tick in range(4):
            tick_response = await client.post(
                "/api/world/tick",
                json={"expected_tick": expected_tick},
            )
            assert tick_response.status_code == 200

        response = await client.get("/api/npcs/ryan")

    assert response.status_code == 200
    recent_actions = response.json()["data"]["recent_actions"]
    assert [action["tick"] for action in recent_actions] == [4, 3, 2]
    assert len(recent_actions) == 3


@pytest.mark.anyio
async def test_get_npc_detail_returns_404_for_unknown_profile(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    transport = ASGITransport(app=create_app(database_url))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/npcs/missing-npc")

    assert response.status_code == 404
    assert response.json() == {
        "success": False,
        "data": None,
        "message": "NPC not found",
    }


@pytest.mark.anyio
async def test_get_npc_detail_returns_safe_503_when_database_is_uninitialized(
    database_url,
):
    transport = ASGITransport(
        app=create_app(database_url),
        raise_app_exceptions=False,
    )
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/npcs/ryan")

    assert response.status_code == 503
    assert response.json() == {
        "success": False,
        "data": None,
        "message": "NPC detail is unavailable",
    }


@pytest.mark.anyio
async def test_get_npc_detail_returns_503_for_profile_without_state(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        state = session.get(NpcState, "ryan")
        assert state is not None
        session.delete(state)
        session.commit()

    transport = ASGITransport(app=create_app(database_url))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/npcs/ryan")

    assert response.status_code == 503
    assert response.json() == {
        "success": False,
        "data": None,
        "message": "NPC detail is unavailable",
    }
