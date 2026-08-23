from uuid import uuid4

from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
import pytest

from backend.app.database.connection import create_engine_and_session
from backend.app.database.models import Conversation, ConversationMessage
from backend.app.llm.provider import ChatProviderError
from backend.app.main import create_app
from scripts.seed_world import seed_database


class _FailingProvider:
    name = "failing"

    async def generate_reply(self, request):
        raise ChatProviderError("private upstream failure")


@pytest.mark.anyio
async def test_post_npc_chat_completes_mock_acceptance_loop(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    transport = ASGITransport(app=create_app(database_url))

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/npcs/ryan/chat",
            json={"message": "你害怕史莱姆吗？"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "ok"
    assert body["data"]["npc_id"] == "ryan"
    assert body["data"]["turn"]["user"]["role"] == "user"
    assert body["data"]["turn"]["user"]["content"] == "你害怕史莱姆吗？"
    assert body["data"]["turn"]["assistant"]["role"] == "assistant"
    assert "史莱姆" in body["data"]["turn"]["assistant"]["content"]
    assert body["data"]["turn"]["assistant"]["emotion"] == "guarded"
    assert body["data"]["provider"] == "mock"
    assert body["data"]["fallback_used"] is False


@pytest.mark.anyio
async def test_post_npc_chat_continues_existing_conversation_and_persists_pairs(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    transport = ASGITransport(app=create_app(database_url))

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post(
            "/api/npcs/shir/chat",
            json={"message": "你好"},
        )
        conversation_id = first.json()["data"]["conversation_id"]
        second = await client.post(
            "/api/npcs/shir/chat",
            json={
                "conversation_id": conversation_id,
                "message": "你喜欢甜点吗？",
            },
        )

    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        conversation_count = session.scalar(
            select(func.count()).select_from(Conversation)
        )
        messages = tuple(
            session.scalars(
                select(ConversationMessage).order_by(ConversationMessage.id)
            )
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["data"]["conversation_id"] == conversation_id
    assert conversation_count == 1
    assert [message.role for message in messages] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    assert messages[-1].emotion == "reserved"


@pytest.mark.anyio
async def test_post_npc_chat_returns_404_for_unknown_npc(database_url, seed_dir):
    seed_database(database_url, seed_dir)
    transport = ASGITransport(app=create_app(database_url))

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/npcs/missing/chat",
            json={"message": "你好"},
        )

    assert response.status_code == 404
    assert response.json() == {
        "success": False,
        "data": None,
        "message": "NPC not found",
    }


@pytest.mark.anyio
async def test_post_npc_chat_returns_404_for_missing_conversation(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    transport = ASGITransport(app=create_app(database_url))

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/npcs/ryan/chat",
            json={"conversation_id": str(uuid4()), "message": "继续聊"},
        )

    assert response.status_code == 404
    assert response.json()["message"] == "Conversation not found"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"message": "   "},
        {"message": "x" * 501},
        {"conversation_id": "not-a-uuid", "message": "你好"},
    ],
)
async def test_post_npc_chat_rejects_invalid_input(database_url, seed_dir, payload):
    seed_database(database_url, seed_dir)
    transport = ASGITransport(app=create_app(database_url))

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/npcs/ryan/chat", json=payload)

    assert response.status_code == 422


@pytest.mark.anyio
async def test_post_npc_chat_returns_safe_503_and_no_rows_on_provider_failure(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    transport = ASGITransport(
        app=create_app(database_url, chat_provider=_FailingProvider())
    )

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/npcs/grey/chat",
            json={"message": "你好"},
        )

    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        conversation_count = session.scalar(
            select(func.count()).select_from(Conversation)
        )
        message_count = session.scalar(
            select(func.count()).select_from(ConversationMessage)
        )

    assert response.status_code == 503
    assert response.json() == {
        "success": False,
        "data": None,
        "message": "Chat service is unavailable",
    }
    assert "private" not in response.text
    assert conversation_count == 0
    assert message_count == 0
