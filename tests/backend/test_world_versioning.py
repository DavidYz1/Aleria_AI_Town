import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from backend.app.core.config import Settings
from backend.app.database.connection import create_engine_and_session
from backend.app.database.models import (
    ConversationMessage,
    PlayerState,
    QuestEvent,
    QuestProgress,
)
from backend.app.main import create_app
from scripts.seed_world import seed_database


def _app(database_url: str):
    return create_app(
        database_url,
        settings=Settings(_env_file=None, database_url=database_url, chat_provider="mock"),
    )


async def _world(client: AsyncClient) -> dict:
    response = await client.get("/api/world")
    assert response.status_code == 200
    return response.json()["data"]["world"]


def _player_quest_history_snapshot(session_factory) -> tuple:
    with session_factory() as session:
        player = session.get(PlayerState, "default-player")
        progress = session.get(
            QuestProgress,
            ("default-player", "missing-child"),
        )
        assert player is not None
        assert progress is not None
        history = tuple(
            (
                event.id,
                event.player_id,
                event.quest_id,
                event.from_status,
                event.to_status,
                event.interaction,
                event.location_id,
                event.clock_tick,
                event.created_at,
            )
            for event in session.scalars(select(QuestEvent).order_by(QuestEvent.id))
        )
        return (
            (
                player.id,
                player.world_id,
                player.location_id,
                player.updated_at,
            ),
            (
                progress.player_id,
                progress.quest_id,
                progress.status,
                progress.version,
                progress.updated_clock_tick,
                progress.updated_at,
            ),
            history,
        )


@pytest.mark.anyio
async def test_time_advance_increments_world_version_and_clock_tick_once(
    database_url, seed_dir
):
    """Removing either world counter increment must fail this contract."""
    seed_database(database_url, seed_dir)
    transport = ASGITransport(app=_app(database_url))

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        before = await _world(client)
        advanced = await client.post(
            "/api/world/tick", json={"expected_world_version": 0}
        )
        after = await _world(client)

    assert advanced.status_code == 200
    assert (after["world_version"] - before["world_version"], after["clock_tick"] - before["clock_tick"]) == (1, 1)
    assert (after["day"], after["time"]) == (1, "09:00")


@pytest.mark.anyio
async def test_player_travel_increments_world_version_without_advancing_clock(
    database_url, seed_dir
):
    """A travel that omits the global bump or advances time must fail."""
    seed_database(database_url, seed_dir)
    transport = ASGITransport(app=_app(database_url))

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        before = await _world(client)
        moved = await client.post(
            "/api/player/travel",
            json={"target_location_id": "castle", "expected_world_version": 0},
        )
        after = await _world(client)

    assert moved.status_code == 200
    assert moved.json()["data"]["player"]["location_id"] == "castle"
    assert (after["world_version"] - before["world_version"], after["clock_tick"] - before["clock_tick"]) == (1, 0)


@pytest.mark.anyio
async def test_same_location_travel_does_not_increment_world_version(
    database_url, seed_dir
):
    """Making idempotent travel mutate a world counter must fail."""
    seed_database(database_url, seed_dir)
    transport = ASGITransport(app=_app(database_url))

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        before = await _world(client)
        same = await client.post(
            "/api/player/travel",
            json={"target_location_id": "tavern", "expected_world_version": 0},
        )
        after = await _world(client)

    assert same.status_code == 200
    assert same.json()["data"]["player"]["location_id"] == "tavern"
    assert (after["world_version"] - before["world_version"], after["clock_tick"] - before["clock_tick"]) == (0, 0)


@pytest.mark.anyio
async def test_quest_transition_increments_world_and_quest_versions_only(
    database_url, seed_dir
):
    """Changing the quest without its global bump, or changing time, must fail."""
    seed_database(database_url, seed_dir)
    transport = ASGITransport(app=_app(database_url))

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        before = await _world(client)
        transitioned = await client.post(
            "/api/quests/missing-child/interact",
            json={
                "interaction": "accept_quest",
                "expected_version": 0,
                "expected_world_version": 0,
            },
        )
        after = await _world(client)

    assert transitioned.status_code == 200
    assert transitioned.json()["data"]["quest"]["version"] == 1
    assert (after["world_version"] - before["world_version"], after["clock_tick"] - before["clock_tick"]) == (1, 0)


@pytest.mark.anyio
async def test_chat_transcript_does_not_change_world_version_or_clock_tick(
    database_url, seed_dir
):
    """Accidentally coupling chat persistence to a global counter must fail."""
    seed_database(database_url, seed_dir)
    transport = ASGITransport(app=_app(database_url))

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        before = await _world(client)
        response = await client.post(
            "/api/npcs/ryan/chat", json={"message": "你好"}
        )
        after = await _world(client)

    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        message_count = session.scalar(select(func.count()).select_from(ConversationMessage))

    assert response.status_code == 200
    assert message_count == 2
    assert (after["world_version"] - before["world_version"], after["clock_tick"] - before["clock_tick"]) == (0, 0)


@pytest.mark.anyio
async def test_stale_world_version_rejects_travel_and_quest_atomically(
    database_url, seed_dir
):
    """Removing either compare-and-swap must permit a stale mutation."""
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    before_state = _player_quest_history_snapshot(session_factory)
    transport = ASGITransport(app=_app(database_url))

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        advanced = await client.post(
            "/api/world/tick", json={"expected_world_version": 0}
        )
        stale_travel = await client.post(
            "/api/player/travel",
            json={"target_location_id": "castle", "expected_world_version": 0},
        )
        stale_quest = await client.post(
            "/api/quests/missing-child/interact",
            json={
                "interaction": "accept_quest",
                "expected_version": 0,
                "expected_world_version": 0,
            },
        )
        after = await _world(client)

    after_state = _player_quest_history_snapshot(session_factory)

    assert advanced.status_code == 200
    assert stale_travel.status_code == stale_quest.status_code == 409
    assert stale_travel.json()["message"] == "world version conflict; refresh and retry"
    assert stale_quest.json()["message"] == "world version conflict; refresh and retry"
    assert (after["world_version"], after["clock_tick"]) == (1, 1)
    assert after_state == before_state
