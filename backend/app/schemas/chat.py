from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


ChatEmotion = Literal[
    "neutral",
    "cheerful",
    "reserved",
    "guarded",
    "thoughtful",
    "concerned",
]


class NpcChatRequest(BaseModel):
    conversation_id: UUID | None = None
    message: str = Field(min_length=1, max_length=500)

    @field_validator("message", mode="before")
    @classmethod
    def strip_message(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class ChatUserMessageData(BaseModel):
    id: int = Field(ge=1)
    role: Literal["user"] = "user"
    content: str = Field(min_length=1, max_length=500)


class ChatAssistantMessageData(BaseModel):
    id: int = Field(ge=1)
    role: Literal["assistant"] = "assistant"
    content: str = Field(min_length=1, max_length=500)
    emotion: ChatEmotion


class ChatTurnData(BaseModel):
    user: ChatUserMessageData
    assistant: ChatAssistantMessageData


class NpcChatData(BaseModel):
    conversation_id: UUID
    npc_id: str = Field(min_length=1)
    turn: ChatTurnData
    provider: str = Field(min_length=1)
    fallback_used: bool
