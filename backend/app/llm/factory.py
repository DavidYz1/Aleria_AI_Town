import httpx

from backend.app.core.config import Settings
from backend.app.llm.fallback import FallbackChatProvider
from backend.app.llm.mock import MockChatProvider
from backend.app.llm.openai_compatible import OpenAICompatibleChatProvider
from backend.app.llm.provider import ChatProvider


def build_chat_provider(
    settings: Settings,
    *,
    client: httpx.AsyncClient | None = None,
) -> ChatProvider:
    mock_provider = MockChatProvider()
    if settings.chat_provider == "mock":
        return mock_provider

    primary = OpenAICompatibleChatProvider(
        name=settings.chat_provider,
        base_url=settings.chat_llm_base_url,
        api_key=settings.chat_llm_api_key,
        model=settings.chat_llm_model,
        auth_mode=settings.chat_llm_auth_mode,
        timeout_seconds=settings.chat_llm_timeout_seconds,
        client=client,
    )
    return FallbackChatProvider(primary, mock_provider)
