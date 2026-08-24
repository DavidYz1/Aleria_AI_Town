import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


ChatEmotion = Literal[
    "neutral",
    "cheerful",
    "reserved",
    "guarded",
    "thoughtful",
    "concerned",
]
AdventurerClass = Literal["mage", "ranger", "cleric"]
PLAYER_NAME_PATTERN = re.compile(
    r"^[A-Za-z0-9\u3400-\u4DBF\u4E00-\u9FFF ·-]+$"
)


class PlayerProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=16)
    adventurer_class: AdventurerClass

    @field_validator("display_name", mode="before")
    @classmethod
    def validate_display_name(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        if not PLAYER_NAME_PATTERN.fullmatch(normalized):
            raise ValueError("Invalid display name")
        return normalized


class NpcChatRequest(BaseModel):
    conversation_id: UUID | None = None
    message: str = Field(min_length=1, max_length=500)
    player_profile: PlayerProfileInput | None = None

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
