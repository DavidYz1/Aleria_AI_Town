import json

import httpx
import pytest

from backend.app.llm.openai_compatible import OpenAICompatibleChatProvider
from backend.app.llm.provider import ChatProviderError
from backend.app.llm.types import (
    ChatActionContext,
    ChatHistoryMessage,
    ChatProviderRequest,
)


def _request() -> ChatProviderRequest:
    return ChatProviderRequest(
        npc_id="ryan",
        npc_name="Ryan",
        role="Knight",
        personality=("optimistic", "brave", "kind"),
        character_prompt="保持 Ryan 乐观、勇敢而友善的性格。",
        world_lore="艾莱瑞亚大陆上的晨曦镇。",
        chat_system_prompt="你是游戏中的 NPC，只返回 JSON。",
        world_id="aleria-town",
        world_name="晨曦镇",
        world_day=1,
        world_time="08:10",
        world_tick=1,
        time_phase="morning",
        location_id="park",
        location_name="中央公园",
        current_action="socialize",
        energy=79,
        mood=80,
        social=72,
        recent_actions=(
            ChatActionContext(
                tick=1,
                world_time="08:10",
                action_type="socialize",
                target_name="Shir",
                reason_code="morning_social",
            ),
        ),
        conversation_history=(
            ChatHistoryMessage(role="user", content="早上好。"),
            ChatHistoryMessage(role="assistant", content="早上好，旅行者。"),
        ),
        player_message="你现在在做什么？",
    )


def _provider(
    handler,
    *,
    auth_mode: str = "bearer",
) -> tuple[OpenAICompatibleChatProvider, httpx.AsyncClient]:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleChatProvider(
        name="deepseek",
        base_url="https://llm.example.test/v1/",
        api_key="secret-key",
        model="chat-model",
        auth_mode=auth_mode,
        timeout_seconds=3,
        client=client,
    )
    return provider, client


@pytest.mark.anyio
async def test_adapter_sends_openai_compatible_request_and_parses_json_reply():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("Authorization")
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "reply": "我正在和 Shir 聊聊今天的安排。",
                                    "emotion": "cheerful",
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
        )

    provider, client = _provider(handler)
    try:
        result = await provider.generate_reply(_request())
    finally:
        await client.aclose()

    assert captured["url"] == "https://llm.example.test/v1/chat/completions"
    assert captured["authorization"] == "Bearer secret-key"
    assert set(captured["body"]) == {"model", "messages", "temperature"}
    assert captured["body"]["model"] == "chat-model"
    assert captured["body"]["temperature"] == 0.2
    assert [message["role"] for message in captured["body"]["messages"]] == [
        "system",
        "user",
        "assistant",
        "user",
    ]
    system_prompt = captured["body"]["messages"][0]["content"]
    assert system_prompt.index("你是游戏中的 NPC") < system_prompt.index("晨曦镇")
    assert system_prompt.index("晨曦镇") < system_prompt.index("保持 Ryan")
    assert "08:10" in system_prompt
    assert "中央公园" in system_prompt
    assert "socialize" in system_prompt
    assert captured["body"]["messages"][-1]["content"] == "你现在在做什么？"
    assert result.reply == "我正在和 Shir 聊聊今天的安排。"
    assert result.emotion == "cheerful"
    assert result.provider == "deepseek"
    assert result.fallback_used is False


@pytest.mark.anyio
async def test_adapter_omits_authorization_for_no_auth_local_service():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers.get("Authorization")
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"reply":"本地服务回复","emotion":"neutral"}'
                        }
                    }
                ]
            },
        )

    provider, client = _provider(handler, auth_mode="none")
    try:
        result = await provider.generate_reply(_request())
    finally:
        await client.aclose()

    assert captured["authorization"] is None
    assert result.reply == "本地服务回复"


@pytest.mark.anyio
@pytest.mark.parametrize("status_code", [400, 401, 429, 500])
async def test_adapter_normalizes_non_success_statuses(status_code):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, text="upstream secret failure details")

    provider, client = _provider(handler)
    try:
        with pytest.raises(ChatProviderError) as caught:
            await provider.generate_reply(_request())
    finally:
        await client.aclose()

    assert str(caught.value) == "Chat provider is unavailable"
    assert "secret" not in str(caught.value)


@pytest.mark.anyio
async def test_adapter_normalizes_transport_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("upstream timed out with secret-key")

    provider, client = _provider(handler)
    try:
        with pytest.raises(ChatProviderError) as caught:
            await provider.generate_reply(_request())
    finally:
        await client.aclose()

    assert str(caught.value) == "Chat provider is unavailable"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "response_json",
    [
        {"unexpected": []},
        {"choices": []},
        {"choices": [{"message": {"content": "not-json"}}]},
        {
            "choices": [
                {
                    "message": {
                        "content": '{"reply":"有效","emotion":"excited"}'
                    }
                }
            ]
        },
        {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"reply":"有效","emotion":"neutral",'
                            '"action":"work"}'
                        )
                    }
                }
            ]
        },
    ],
)
async def test_adapter_normalizes_malformed_or_untrusted_payloads(response_json):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=response_json)

    provider, client = _provider(handler)
    try:
        with pytest.raises(ChatProviderError) as caught:
            await provider.generate_reply(_request())
    finally:
        await client.aclose()

    assert str(caught.value) == "Chat provider is unavailable"


@pytest.mark.anyio
async def test_adapter_does_not_close_an_injected_client():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"reply":"有效","emotion":"neutral"}'
                        }
                    }
                ]
            },
        )

    provider, client = _provider(handler)
    await provider.generate_reply(_request())

    assert client.is_closed is False
    await client.aclose()
