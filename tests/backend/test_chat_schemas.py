from uuid import UUID

import pytest
from pydantic import ValidationError

from backend.app.schemas.chat import (
    ChatAssistantMessageData,
    ChatTurnData,
    ChatUserMessageData,
    NpcChatData,
    NpcChatRequest,
)


CONVERSATION_ID = "5e547c21-a228-4e86-940d-a1bf5d65702f"


def test_chat_request_strips_message_for_a_new_conversation():
    request = NpcChatRequest(
        conversation_id=None,
        message="  你好，Ryan  ",
    )

    assert request.conversation_id is None
    assert request.message == "你好，Ryan"


@pytest.mark.parametrize("message", ["", " ", "\n\t"])
def test_chat_request_rejects_blank_message(message):
    with pytest.raises(ValidationError):
        NpcChatRequest(conversation_id=None, message=message)


def test_chat_request_rejects_message_longer_than_five_hundred_characters():
    with pytest.raises(ValidationError):
        NpcChatRequest(conversation_id=None, message="你" * 501)


def test_chat_request_rejects_malformed_conversation_id():
    with pytest.raises(ValidationError):
        NpcChatRequest(conversation_id="not-a-uuid", message="你好")


def test_chat_response_serializes_the_persisted_turn_contract():
    response = NpcChatData(
        conversation_id=CONVERSATION_ID,
        npc_id="ryan",
        turn=ChatTurnData(
            user=ChatUserMessageData(
                id=1,
                content="你害怕史莱姆吗？",
            ),
            assistant=ChatAssistantMessageData(
                id=2,
                content="害怕？当然不是……",
                emotion="guarded",
            ),
        ),
        provider="mock",
        fallback_used=False,
    )

    assert response.conversation_id == UUID(CONVERSATION_ID)
    assert response.model_dump(mode="json") == {
        "conversation_id": CONVERSATION_ID,
        "npc_id": "ryan",
        "turn": {
            "user": {
                "id": 1,
                "role": "user",
                "content": "你害怕史莱姆吗？",
            },
            "assistant": {
                "id": 2,
                "role": "assistant",
                "content": "害怕？当然不是……",
                "emotion": "guarded",
            },
        },
        "provider": "mock",
        "fallback_used": False,
    }


@pytest.mark.parametrize(
    ("content", "emotion"),
    [
        ("", "neutral"),
        ("答" * 501, "neutral"),
        ("有效回复", "excited"),
    ],
)
def test_chat_assistant_message_rejects_invalid_provider_output(
    content,
    emotion,
):
    with pytest.raises(ValidationError):
        ChatAssistantMessageData(
            id=2,
            content=content,
            emotion=emotion,
        )
