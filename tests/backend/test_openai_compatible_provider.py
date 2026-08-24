import json
import logging
from dataclasses import replace

import httpx
import pytest

from backend.app.llm.openai_compatible import OpenAICompatibleChatProvider
from backend.app.llm.provider import ChatProviderError
from backend.app.llm.types import (
    ChatActionContext,
    ChatHistoryMessage,
    ChatProviderRequest,
    PlayerQuestChatContext,
)


def _request() -> ChatProviderRequest:
    return ChatProviderRequest(
        npc_id="ryan",
        npc_name="Ryan",
        role="Knight",
        personality=("optimistic", "brave", "kind"),
        character_prompt="保持 Ryan 乐观、勇敢而友善的性格。",
        world_lore="幻想大陆上的曦谷。",
        chat_system_prompt="你是游戏中的 NPC，只返回 JSON。",
        player_context_prompt="玩家是新到曦谷的旅行者，不得擅自补全身份。",
        world_id="aleria-town",
        world_name="曦谷",
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
        player_quest_context=PlayerQuestChatContext(
            player_id="player-1",
            location_id="tavern",
            location_name="星辉酒馆",
            quest_id="missing-child",
            quest_status="accepted",
            quest_objective="去曦谷城堡向 Grey 询问失踪孩子的线索",
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
    output_mode: str = "structured_json",
) -> tuple[OpenAICompatibleChatProvider, httpx.AsyncClient]:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleChatProvider(
        name="deepseek",
        base_url="https://llm.example.test/v1/",
        api_key="secret-key",
        model="chat-model",
        auth_mode=auth_mode,
        output_mode=output_mode,
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
    assert system_prompt.index("你是游戏中的 NPC") < system_prompt.index("幻想大陆")
    assert system_prompt.index("幻想大陆") < system_prompt.index("玩家是新到曦谷")
    assert system_prompt.index("玩家是新到曦谷") < system_prompt.index("保持 Ryan")
    assert "08:10" in system_prompt
    assert "中央公园" in system_prompt
    assert "socialize" in system_prompt
    assert "missing-child" in system_prompt
    assert "去曦谷城堡向 Grey 询问失踪孩子的线索" in system_prompt
    assert "Return exactly one JSON object" in system_prompt
    assert captured["body"]["messages"][-1]["content"] == "你现在在做什么？"
    assert result.reply == "我正在和 Shir 聊聊今天的安排。"
    assert result.emotion == "cheerful"
    assert result.provider == "deepseek"
    assert result.fallback_used is False


@pytest.mark.anyio
async def test_adapter_text_mode_parses_natural_reply_without_extra_body_fields():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": "  别急，先说孩子最后出现在哪里。  "}}
                ]
            },
        )

    provider, client = _provider(handler, output_mode="text")
    try:
        result = await provider.generate_reply(_request())
    finally:
        await client.aclose()

    assert set(captured["body"]) == {"model", "messages", "temperature"}
    assert "response_format" not in captured["body"]
    system_prompt = captured["body"]["messages"][0]["content"]
    assert "只返回 NPC 的自然回复正文" in system_prompt
    assert "不要 JSON" in system_prompt
    assert result.reply == "别急，先说孩子最后出现在哪里。"
    assert result.emotion == "cheerful"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("npc_id", "mood", "expected_emotion"),
    [
        ("ryan", 78, "cheerful"),
        ("shir", 78, "reserved"),
        ("grey", 78, "thoughtful"),
        ("future-resident", 78, "neutral"),
        ("ryan", 35, "concerned"),
    ],
)
async def test_adapter_text_mode_derives_safe_emotion_from_context(
    npc_id,
    mood,
    expected_emotion,
):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "有效自然回复"}}]},
        )

    provider, client = _provider(handler, output_mode="text")
    request = replace(_request(), npc_id=npc_id, mood=mood)
    try:
        result = await provider.generate_reply(request)
    finally:
        await client.aclose()

    assert result.emotion == expected_emotion


@pytest.mark.anyio
@pytest.mark.parametrize("content", [None, "", "   ", "答" * 501])
async def test_adapter_text_mode_rejects_invalid_content_as_response_validation(
    caplog,
    content,
):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": content}}]},
        )

    provider, client = _provider(handler, output_mode="text")
    try:
        with caplog.at_level(
            logging.WARNING,
            logger="backend.app.llm.openai_compatible",
        ):
            with pytest.raises(ChatProviderError):
                await provider.generate_reply(_request())
    finally:
        await client.aclose()

    assert caplog.records[-1].category == "response_validation"
    assert "答答答" not in caplog.text


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
async def test_adapter_classifies_http_failure_without_logging_upstream_details(
    caplog,
):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="upstream-secret-response")

    provider, client = _provider(handler)
    try:
        with caplog.at_level(
            logging.WARNING,
            logger="backend.app.llm.openai_compatible",
        ):
            with pytest.raises(ChatProviderError):
                await provider.generate_reply(_request())
    finally:
        await client.aclose()

    record = caplog.records[-1]
    assert record.provider == "deepseek"
    assert record.category == "http_status"
    assert record.status_code == 401
    assert (
        "provider=deepseek category=http_status status=401"
        in caplog.text
    )
    assert "upstream-secret-response" not in caplog.text
    assert "secret-key" not in caplog.text


@pytest.mark.anyio
async def test_adapter_classifies_timeout_without_logging_exception_details(caplog):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout included secret-key")

    provider, client = _provider(handler)
    try:
        with caplog.at_level(
            logging.WARNING,
            logger="backend.app.llm.openai_compatible",
        ):
            with pytest.raises(ChatProviderError):
                await provider.generate_reply(_request())
    finally:
        await client.aclose()

    record = caplog.records[-1]
    assert record.provider == "deepseek"
    assert record.category == "timeout"
    assert record.status_code is None
    assert "timeout included secret-key" not in caplog.text
    assert "secret-key" not in caplog.text


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("response", "expected_category"),
    [
        (httpx.Response(200, text="not-json"), "response_json"),
        (httpx.Response(200, json={"unexpected": []}), "response_shape"),
        (
            httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"content": "not-json"}},
                    ]
                },
            ),
            "response_validation",
        ),
    ],
)
async def test_adapter_classifies_unsafe_response_without_logging_its_body(
    caplog,
    response,
    expected_category,
):
    def handler(request: httpx.Request) -> httpx.Response:
        return response

    provider, client = _provider(handler)
    try:
        with caplog.at_level(
            logging.WARNING,
            logger="backend.app.llm.openai_compatible",
        ):
            with pytest.raises(ChatProviderError):
                await provider.generate_reply(_request())
    finally:
        await client.aclose()

    record = caplog.records[-1]
    assert record.provider == "deepseek"
    assert record.category == expected_category
    assert record.status_code is None
    assert "not-json" not in caplog.text


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
