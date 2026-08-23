from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.llm.types import ChatProviderRequest
from backend.app.schemas.chat import ChatEmotion


PROVIDER_UNAVAILABLE_MESSAGE = "Chat provider is unavailable"


class ChatProviderError(RuntimeError):
    pass


class ChatProviderResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    reply: str = Field(min_length=1, max_length=500)
    emotion: ChatEmotion
    provider: str = Field(min_length=1)
    fallback_used: bool = False

    @field_validator("reply", "provider", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class ChatProvider(Protocol):
    name: str

    async def generate_reply(
        self,
        request: ChatProviderRequest,
    ) -> ChatProviderResult:
        ...
