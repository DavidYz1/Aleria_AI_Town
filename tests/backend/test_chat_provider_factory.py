import json

import httpx
import pytest

from backend.app.core.config import Settings
from backend.app.llm.factory import build_chat_provider
from backend.app.llm.fallback import FallbackChatProvider
from backend.app.llm.mock import MockChatProvider
from backend.app.llm.provider import ChatProviderError, ChatProviderResult
from backend.app.llm.types import ChatProviderRequest


def _request() -> ChatProviderRequest:
    return ChatProviderRequest(
        npc_id="ryan",
        npc_name="Ryan",
        role="Knight",
        personality=("optimistic",),
        character_prompt="Ryan character prompt",
        world_lore="曦谷",
        chat_system_prompt="Return JSON",
        player_context_prompt="玩家是旅行者",
        world_id="aleria-town",
        world_name="曦谷",
        world_day=1,
        world_time="08:00",
        world_tick=0,
        time_phase="morning",
        location_id="park",
        location_name="中央公园",
        current_action="rest",
        energy=80,
        mood=78,
        social=70,
        recent_actions=(),
        player_quest_context=None,
        conversation_history=(),
        player_message="你好",
    )


class _StubProvider:
    def __init__(
        self,
        *,
        name: str,
        result: ChatProviderResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.name = name
        self.result = result
        self.error = error
        self.calls = 0

    async def generate_reply(self, request):
        self.calls += 1
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def test_factory_builds_mock_without_llm_connection_details():
    provider = build_chat_provider(Settings(_env_file=None))

    assert isinstance(provider, MockChatProvider)
    assert provider.name == "mock"


@pytest.mark.anyio
@pytest.mark.parametrize("provider_name", ["hunyuan", "deepseek", "local"])
async def test_factory_routes_all_non_mock_labels_through_one_compatible_adapter(
    provider_name,
):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {"reply": "模型回复", "emotion": "neutral"},
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    settings = Settings(
        _env_file=None,
        chat_provider=provider_name,
        chat_llm_base_url="https://llm.example.test/v1",
        chat_llm_api_key="secret",
        chat_llm_model="model",
    )
    provider = build_chat_provider(settings, client=client)
    try:
        result = await provider.generate_reply(_request())
    finally:
        await client.aclose()

    assert isinstance(provider, FallbackChatProvider)
    assert provider.name == provider_name
    assert result.provider == provider_name
    assert result.fallback_used is False


@pytest.mark.anyio
async def test_factory_passes_text_output_mode_to_the_same_compatible_adapter():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert set(body) == {"model", "messages", "temperature"}
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "自然文本回复"}}]},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    settings = Settings(
        _env_file=None,
        chat_provider="hunyuan",
        chat_llm_base_url="https://llm.example.test/v1",
        chat_llm_api_key="secret",
        chat_llm_model="hy-role",
        chat_llm_output_mode="text",
    )
    provider = build_chat_provider(settings, client=client)
    try:
        result = await provider.generate_reply(_request())
    finally:
        await client.aclose()

    assert isinstance(provider, FallbackChatProvider)
    assert result.reply == "自然文本回复"
    assert result.provider == "hunyuan"
    assert result.fallback_used is False


@pytest.mark.anyio
async def test_fallback_returns_primary_result_unchanged_on_success():
    expected = ChatProviderResult(
        reply="primary",
        emotion="neutral",
        provider="primary",
    )
    primary = _StubProvider(name="primary", result=expected)
    fallback = _StubProvider(
        name="mock",
        result=ChatProviderResult(
            reply="fallback",
            emotion="neutral",
            provider="mock",
        ),
    )

    result = await FallbackChatProvider(primary, fallback).generate_reply(_request())

    assert result is expected
    assert primary.calls == 1
    assert fallback.calls == 0


@pytest.mark.anyio
async def test_fallback_uses_mock_only_for_normalized_provider_errors():
    primary = _StubProvider(
        name="primary",
        error=ChatProviderError("Chat provider is unavailable"),
    )
    fallback = _StubProvider(
        name="mock",
        result=ChatProviderResult(
            reply="fallback",
            emotion="thoughtful",
            provider="mock",
        ),
    )

    result = await FallbackChatProvider(primary, fallback).generate_reply(_request())

    assert result.reply == "fallback"
    assert result.provider == "mock"
    assert result.fallback_used is True
    assert primary.calls == 1
    assert fallback.calls == 1


@pytest.mark.anyio
async def test_fallback_does_not_hide_programming_errors():
    primary = _StubProvider(name="primary", error=ValueError("bug"))
    fallback = _StubProvider(
        name="mock",
        result=ChatProviderResult(
            reply="fallback",
            emotion="neutral",
            provider="mock",
        ),
    )

    with pytest.raises(ValueError, match="bug"):
        await FallbackChatProvider(primary, fallback).generate_reply(_request())

    assert fallback.calls == 0


@pytest.mark.anyio
async def test_fallback_normalizes_failure_of_both_providers():
    primary = _StubProvider(
        name="primary",
        error=ChatProviderError("primary detail"),
    )
    fallback = _StubProvider(
        name="mock",
        error=ChatProviderError("fallback detail"),
    )

    with pytest.raises(ChatProviderError) as caught:
        await FallbackChatProvider(primary, fallback).generate_reply(_request())

    assert str(caught.value) == "Chat provider is unavailable"
