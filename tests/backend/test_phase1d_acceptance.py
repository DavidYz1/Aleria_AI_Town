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
    QuestEvent,
    QuestProgress,
    WorldAction,
    WorldState,
)
from backend.app.llm.fallback import FallbackChatProvider
from backend.app.llm.mock import MockChatProvider
from backend.app.llm.provider import (
    ChatProviderError,
    ChatProviderResult,
)
from backend.app.main import create_app
from scripts.seed_world import seed_database


class _CapturingProvider:
    name = "acceptance-provider"

    def __init__(self) -> None:
        self.requests = []

    async def generate_reply(self, request):
        self.requests.append(request)
        return ChatProviderResult(
            reply=f"当前目标：{request.player_quest_context.quest_objective}",
            emotion="thoughtful",
            provider=self.name,
        )


class _UnavailableProvider:
    name = "unavailable-primary"

    async def generate_reply(self, request):
        raise ChatProviderError("private upstream detail")


def _settings(database_url: str) -> Settings:
    return Settings(
        _env_file=None,
        database_url=database_url,
        chat_provider="mock",
    )


def _world_snapshot(session_factory):
    with session_factory() as session:
        world = session.get(WorldState, "aleria-town")
        assert world is not None
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
            "events": session.scalar(select(func.count()).select_from(Event)),
        }


def _quest_snapshot(session_factory):
    with session_factory() as session:
        player = session.get(PlayerState, "default-player")
        progress = session.get(
            QuestProgress,
            ("default-player", "missing-child"),
        )
        assert player is not None
        assert progress is not None
        return (
            player.location_id,
            progress.status,
            progress.version,
            session.scalar(select(func.count()).select_from(QuestEvent)),
        )


def _message_count(session_factory) -> int:
    with session_factory() as session:
        return session.scalar(
            select(func.count()).select_from(ConversationMessage)
        )


async def _interact(client: AsyncClient, interaction: str, version: int):
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
async def test_phase1d_mock_path_completes_and_persists_without_world_mutation(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    world_before = _world_snapshot(session_factory)
    app = create_app(database_url, settings=_settings(database_url))

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        world_response = await client.get("/api/world")
        initial_response = await client.get("/api/player")

        await _interact(client, "accept_quest", 0)
        await _travel(client, "castle")
        await _interact(client, "ask_grey", 1)
        await _travel(client, "forest")
        await _interact(client, "inspect_shoe", 2)
        await _interact(client, "search_child", 3)
        await _travel(client, "tavern")
        await _interact(client, "return_child", 4)
        completed_response = await client.get("/api/player")

    assert world_response.status_code == 200
    world_data = world_response.json()["data"]
    assert world_data["world"]["name"] == "曦谷"
    assert [item["id"] for item in world_data["locations"]] == [
        "tavern",
        "park",
        "castle",
        "forest",
    ]
    assert [item["id"] for item in world_data["npcs"]] == [
        "ryan",
        "shir",
        "grey",
    ]

    initial = initial_response.json()["data"]
    assert initial["player"]["location_id"] == "tavern"
    assert (initial["quest"]["status"], initial["quest"]["version"]) == (
        "available",
        0,
    )

    completed = completed_response.json()["data"]
    assert completed["player"]["location_id"] == "tavern"
    assert (completed["quest"]["status"], completed["quest"]["version"]) == (
        "completed",
        5,
    )
    assert len(completed["quest"]["recent_events"]) == 5
    assert _world_snapshot(session_factory) == world_before

    fresh_app = create_app(database_url, settings=_settings(database_url))
    async with AsyncClient(
        transport=ASGITransport(app=fresh_app),
        base_url="http://test",
    ) as client:
        persisted_response = await client.get("/api/player")

    persisted = persisted_response.json()["data"]
    assert persisted["quest"] == completed["quest"]
    assert persisted["player"] == completed["player"]


@pytest.mark.anyio
async def test_chat_and_fallback_read_quest_context_without_mutating_game_state(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    world_before = _world_snapshot(session_factory)
    provider = _CapturingProvider()
    app = create_app(
        database_url,
        settings=_settings(database_url),
        chat_provider=provider,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        await _interact(client, "accept_quest", 0)
        await _travel(client, "castle")
        accepted_before = _quest_snapshot(session_factory)
        messages_before = _message_count(session_factory)
        accepted_chat = await client.post(
            "/api/npcs/grey/chat",
            json={"conversation_id": None, "message": "当前任务是什么？"},
        )
        accepted_after = _quest_snapshot(session_factory)

        await _interact(client, "ask_grey", 1)
        briefed_before = _quest_snapshot(session_factory)
        briefed_chat = await client.post(
            "/api/npcs/grey/chat",
            json={"conversation_id": None, "message": "下一步做什么？"},
        )
        briefed_after = _quest_snapshot(session_factory)

    assert accepted_chat.status_code == 200
    assert briefed_chat.status_code == 200
    assert provider.requests[0].player_quest_context.quest_objective == (
        "前往晨曦城堡询问 Grey。"
    )
    assert provider.requests[1].player_quest_context.quest_objective == (
        "前往低语森林寻找线索。"
    )
    assert accepted_after == accepted_before
    assert briefed_after == briefed_before
    assert _message_count(session_factory) == messages_before + 4

    fallback = FallbackChatProvider(
        _UnavailableProvider(),
        MockChatProvider(),
    )
    fallback_app = create_app(
        database_url,
        settings=_settings(database_url),
        chat_provider=fallback,
    )
    fallback_before = _quest_snapshot(session_factory)
    messages_before_fallback = _message_count(session_factory)
    async with AsyncClient(
        transport=ASGITransport(app=fallback_app),
        base_url="http://test",
    ) as client:
        fallback_response = await client.post(
            "/api/npcs/grey/chat",
            json={"conversation_id": None, "message": "任务线索是什么？"},
        )

    assert fallback_response.status_code == 200
    assert fallback_response.json()["data"]["provider"] == "mock"
    assert fallback_response.json()["data"]["fallback_used"] is True
    assert _quest_snapshot(session_factory) == fallback_before
    assert _message_count(session_factory) == messages_before_fallback + 2
    assert _world_snapshot(session_factory) == world_before
