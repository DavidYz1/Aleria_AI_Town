from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import func, select

from backend.app.core.config import Settings
from backend.app.database.connection import create_engine_and_session
from backend.app.database.models import (
    ConversationMessage,
    Event,
    NpcState,
    PlayerState,
    QuestProgress,
    WorldAction,
    WorldState,
)
from backend.app.main import create_app
from scripts.seed_world import seed_database


def _settings(database_url: str) -> Settings:
    return Settings(
        _env_file=None,
        database_url=database_url,
        chat_provider="mock",
        chat_prompt_version="v3",
    )


def _game_snapshot(session_factory):
    with session_factory() as session:
        world = session.get(WorldState, "aleria-town")
        player = session.get(PlayerState, "default-player")
        quest = session.get(
            QuestProgress,
            ("default-player", "missing-child"),
        )
        assert world is not None
        assert player is not None
        assert quest is not None
        return {
            "world": (world.day, world.time, world.tick),
            "npcs": tuple(
                (
                    state.npc_id,
                    state.location_id,
                    state.current_action,
                    state.energy,
                    state.mood,
                    state.social,
                )
                for state in session.scalars(
                    select(NpcState).order_by(NpcState.npc_id)
                )
            ),
            "actions": session.scalar(
                select(func.count()).select_from(WorldAction)
            ),
            "events": session.scalar(
                select(func.count()).select_from(Event)
            ),
            "player": player.location_id,
            "quest": (quest.status, quest.version, quest.updated_tick),
        }


def _message_count(session_factory) -> int:
    with session_factory() as session:
        return session.scalar(
            select(func.count()).select_from(ConversationMessage)
        )


async def _interact(
    client: AsyncClient,
    interaction: str,
    version: int,
):
    response = await client.post(
        "/api/quests/missing-child/interact",
        json={"interaction": interaction, "expected_version": version},
    )
    assert response.status_code == 200
    return response.json()["data"]


async def _travel(client: AsyncClient, location_id: str):
    response = await client.post(
        "/api/player/travel",
        json={"target_location_id": location_id},
    )
    assert response.status_code == 200
    return response.json()["data"]


@pytest.mark.anyio
async def test_phase1e_v3_mock_replies_are_distinct_and_game_state_is_read_only(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    before = _game_snapshot(session_factory)
    app = create_app(database_url, settings=_settings(database_url))

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        responses = [
            await client.post(
                f"/api/npcs/{npc_id}/chat",
                json={"message": "历史书可信吗？"},
            )
            for npc_id in ("ryan", "shir", "grey")
        ]

    assert all(response.status_code == 200 for response in responses)
    data = [response.json()["data"] for response in responses]
    replies = [item["turn"]["assistant"]["content"] for item in data]
    assert len(set(replies)) == 3
    assert all(item["provider"] == "mock" for item in data)
    assert all(item["fallback_used"] is False for item in data)
    assert _message_count(session_factory) == 6
    assert _game_snapshot(session_factory) == before


@pytest.mark.anyio
async def test_phase1e_missing_child_story_uses_existing_five_transitions(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    app = create_app(database_url, settings=_settings(database_url))

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        await _interact(client, "accept_quest", 0)
        await _travel(client, "castle")
        await _interact(client, "ask_grey", 1)
        await _travel(client, "forest")
        await _interact(client, "inspect_shoe", 2)
        await _interact(client, "search_child", 3)
        await _travel(client, "tavern")
        completed = await _interact(client, "return_child", 4)

    quest = completed["quest"]
    descriptions = [
        event["description"] for event in quest["recent_events"]
    ]
    assert (quest["status"], quest["version"]) == ("completed", 5)
    assert len(descriptions) == 5
    assert "旧封锁线" in descriptions[1]
    assert "身上的印记" in descriptions[2]
    assert "林中传来的低语" in descriptions[3]
    assert "印记之谜" in descriptions[4]
    assert "鞋边印记仍没有答案" in quest["objective"]
