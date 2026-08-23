from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
import pytest

from backend.app.core.config import Settings
from backend.app.database.connection import create_engine_and_session
from backend.app.database.models import (
    ConversationMessage,
    Event,
    WorldAction,
)
from backend.app.llm.fallback import FallbackChatProvider
from backend.app.llm.mock import MockChatProvider
from backend.app.llm.provider import ChatProviderError
from backend.app.main import create_app
from scripts.seed_world import seed_database


class _UnavailablePrimaryProvider:
    name = "configured-primary"

    async def generate_reply(self, request):
        raise ChatProviderError("private upstream detail")


def _mock_settings(database_url: str) -> Settings:
    return Settings(
        _env_file=None,
        database_url=database_url,
        chat_provider="mock",
    )


@pytest.mark.anyio
async def test_no_key_mock_chat_preserves_world_across_two_turns(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    settings = _mock_settings(database_url)
    assert settings.chat_llm_base_url == ""
    assert settings.chat_llm_api_key == ""
    assert settings.chat_llm_model == ""

    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        action_count_before = session.scalar(
            select(func.count()).select_from(WorldAction)
        )
        event_count_before = session.scalar(
            select(func.count()).select_from(Event)
        )

    transport = ASGITransport(
        app=create_app(database_url, settings=settings),
    )
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        world_before_response = await client.get("/api/world")
        first = await client.post(
            "/api/npcs/ryan/chat",
            json={"conversation_id": None, "message": "你害怕史莱姆吗？"},
        )
        conversation_id = first.json()["data"]["conversation_id"]
        second = await client.post(
            "/api/npcs/ryan/chat",
            json={
                "conversation_id": conversation_id,
                "message": "那我们该怎么应对？",
            },
        )
        world_after_response = await client.get("/api/world")

    with session_factory() as session:
        message_count = session.scalar(
            select(func.count()).select_from(ConversationMessage)
        )
        action_count_after = session.scalar(
            select(func.count()).select_from(WorldAction)
        )
        event_count_after = session.scalar(
            select(func.count()).select_from(Event)
        )

    assert world_before_response.status_code == 200
    assert first.status_code == 200
    assert second.status_code == 200
    assert world_after_response.status_code == 200
    assert first.json()["data"]["provider"] == "mock"
    assert second.json()["data"]["conversation_id"] == conversation_id
    assert message_count == 4
    assert world_after_response.json()["data"] == world_before_response.json()["data"]
    assert action_count_after == action_count_before
    assert event_count_after == event_count_before


@pytest.mark.anyio
async def test_same_mock_question_produces_distinct_character_replies(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    settings = _mock_settings(database_url)
    transport = ASGITransport(
        app=create_app(database_url, settings=settings),
    )

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        responses = [
            await client.post(
                f"/api/npcs/{npc_id}/chat",
                json={"conversation_id": None, "message": "今天过得怎么样？"},
            )
            for npc_id in ("ryan", "shir", "grey")
        ]

    assert [response.status_code for response in responses] == [200, 200, 200]
    replies = [
        response.json()["data"]["turn"]["assistant"]["content"]
        for response in responses
    ]
    assert len(set(replies)) == 3
    assert [response.json()["data"]["npc_id"] for response in responses] == [
        "ryan",
        "shir",
        "grey",
    ]


@pytest.mark.anyio
async def test_primary_failure_falls_back_and_persists_truthful_metadata(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    provider = FallbackChatProvider(
        _UnavailablePrimaryProvider(),
        MockChatProvider(),
    )
    transport = ASGITransport(
        app=create_app(
            database_url,
            settings=_mock_settings(database_url),
            chat_provider=provider,
        ),
    )

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/npcs/grey/chat",
            json={"conversation_id": None, "message": "你好"},
        )

    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        assistant = session.scalar(
            select(ConversationMessage).where(
                ConversationMessage.role == "assistant"
            )
        )

    assert response.status_code == 200
    assert response.json()["data"]["provider"] == "mock"
    assert response.json()["data"]["fallback_used"] is True
    assert assistant is not None
    assert assistant.provider == "mock"
    assert assistant.fallback_used == 1
