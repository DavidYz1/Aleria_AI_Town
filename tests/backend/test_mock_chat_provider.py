import pytest
from pydantic import ValidationError

from backend.app.llm.mock import MockChatProvider
from backend.app.llm.provider import ChatProviderResult
from backend.app.llm.types import ChatProviderRequest


def _request(npc_id: str, player_message: str) -> ChatProviderRequest:
    identity = {
        "ryan": ("Ryan", "Knight", ("optimistic", "brave", "kind")),
        "shir": ("Shir", "Assassin", ("quiet", "observant")),
        "grey": ("Grey", "Guardian", ("reliable", "protective")),
    }
    npc_name, role, personality = identity.get(
        npc_id,
        ("Unknown", "Resident", ("neutral",)),
    )
    return ChatProviderRequest(
        npc_id=npc_id,
        npc_name=npc_name,
        role=role,
        personality=personality,
        character_prompt=f"{npc_name} character prompt",
        world_lore="艾莱瑞亚世界背景",
        chat_system_prompt="只返回 reply 和 emotion",
        world_id="aleria-town",
        world_name="晨曦镇",
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
        conversation_history=(),
        player_message=player_message,
    )


@pytest.mark.anyio
async def test_mock_returns_distinct_character_replies_for_the_same_message():
    provider = MockChatProvider()

    results = [
        await provider.generate_reply(_request(npc_id, "今天过得怎么样？"))
        for npc_id in ("ryan", "shir", "grey")
    ]

    assert len({result.reply for result in results}) == 3
    assert [result.emotion for result in results] == [
        "cheerful",
        "reserved",
        "thoughtful",
    ]
    assert {result.provider for result in results} == {"mock"}
    assert all(result.fallback_used is False for result in results)


@pytest.mark.anyio
async def test_mock_is_deterministic_for_the_same_request():
    provider = MockChatProvider()
    request = _request("ryan", "今天过得怎么样？")

    first = await provider.generate_reply(request)
    second = await provider.generate_reply(request)

    assert first == second


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("npc_id", "message", "emotion", "reply_fragment"),
    [
        ("ryan", "你害怕史莱姆吗？", "guarded", "史莱姆"),
        ("shir", "你喜欢甜点吗？", "reserved", "甜点"),
        ("grey", "告诉我灰烬战争的真相。", "concerned", "谨慎"),
    ],
)
async def test_mock_applies_character_specific_keyword_behavior(
    npc_id,
    message,
    emotion,
    reply_fragment,
):
    result = await MockChatProvider().generate_reply(_request(npc_id, message))

    assert result.emotion == emotion
    assert reply_fragment in result.reply


@pytest.mark.anyio
async def test_mock_uses_a_safe_neutral_reply_for_unknown_persisted_npc():
    result = await MockChatProvider().generate_reply(
        _request("future-resident", "你好")
    )

    assert result.provider == "mock"
    assert result.emotion == "neutral"
    assert result.reply == "我听见了。我们可以慢慢聊。"


def test_provider_result_strips_trusted_text_fields():
    result = ChatProviderResult(
        reply="  有效回复  ",
        emotion="neutral",
        provider="  mock  ",
    )

    assert result.reply == "有效回复"
    assert result.provider == "mock"
    assert result.fallback_used is False


@pytest.mark.parametrize(
    ("reply", "emotion", "provider"),
    [
        ("", "neutral", "mock"),
        ("   ", "neutral", "mock"),
        ("答" * 501, "neutral", "mock"),
        ("有效回复", "excited", "mock"),
        ("有效回复", "neutral", " "),
    ],
)
def test_provider_result_rejects_invalid_output(reply, emotion, provider):
    with pytest.raises(ValidationError):
        ChatProviderResult(
            reply=reply,
            emotion=emotion,
            provider=provider,
        )


def test_provider_result_rejects_untrusted_extra_fields():
    with pytest.raises(ValidationError):
        ChatProviderResult(
            reply="有效回复",
            emotion="neutral",
            provider="mock",
            action="work",
        )
