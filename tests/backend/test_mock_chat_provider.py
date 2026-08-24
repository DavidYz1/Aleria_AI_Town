import pytest
from pydantic import ValidationError

from backend.app.llm.mock import MockChatProvider
from backend.app.llm.provider import ChatProviderResult
from backend.app.llm.types import (
    ChatProviderRequest,
    PlayerProfileChatContext,
    PlayerQuestChatContext,
)


def _request(
    npc_id: str,
    player_message: str,
    *,
    player_quest_context: PlayerQuestChatContext | None = None,
    player_profile: PlayerProfileChatContext | None = None,
) -> ChatProviderRequest:
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
        world_lore="曦谷世界背景",
        chat_system_prompt="只返回 reply 和 emotion",
        player_context_prompt="玩家是新到曦谷的旅行者",
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
        player_quest_context=player_quest_context,
        conversation_history=(),
        player_message=player_message,
        player_profile=player_profile,
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
    ("message", "fact_fragment"),
    [
        ("你好", None),
        ("你是谁", None),
        ("这里是哪里", "曦谷"),
        ("你现在在哪里", "中央公园"),
        ("你在做什么", "休息"),
        ("你心情怎么样", "心情"),
        ("我需要帮助", "帮"),
        ("灰烬战争发生了什么", "战争"),
    ],
)
async def test_mock_common_intents_are_deterministic_characterful_and_grounded(
    message,
    fact_fragment,
):
    provider = MockChatProvider()
    requests = [_request(npc_id, message) for npc_id in ("ryan", "shir", "grey")]

    first_results = [
        await provider.generate_reply(request) for request in requests
    ]
    second_results = [
        await provider.generate_reply(request) for request in requests
    ]

    assert first_results == second_results
    assert len({result.reply for result in first_results}) == 3
    assert all("晨曦镇" not in result.reply for result in first_results)
    assert all("星辰酒馆" not in result.reply for result in first_results)
    if fact_fragment is not None:
        assert all(fact_fragment in result.reply for result in first_results)
    if message == "你是谁":
        assert all(
            request.npc_name in result.reply
            for request, result in zip(requests, first_results, strict=True)
        )


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("message", "fact_fragment"),
    [
        ("你认识我吗，我是谁？", "记忆"),
        ("我身上的印记是什么？", "印记"),
        ("终焉战争和古族是什么？", "历史"),
    ],
)
async def test_mock_story_intents_respect_character_and_knowledge_boundaries(
    message,
    fact_fragment,
):
    provider = MockChatProvider()
    results = [
        await provider.generate_reply(_request(npc_id, message))
        for npc_id in ("ryan", "shir", "grey")
    ]

    assert len({result.reply for result in results}) == 3
    assert all(fact_fragment in result.reply for result in results)
    assert all("我知道你的真实身份" not in result.reply for result in results)
    assert all("五百年前我亲眼见过" not in result.reply for result in results)


@pytest.mark.anyio
@pytest.mark.parametrize("npc_id", ["ryan", "shir", "grey"])
async def test_mock_uses_player_name_and_title_for_greetings(npc_id):
    profile = PlayerProfileChatContext(
        display_name="洛恩",
        adventurer_class="ranger",
        class_title="游侠",
    )

    result = await MockChatProvider().generate_reply(
        _request(npc_id, "你好", player_profile=profile)
    )

    assert "洛恩" in result.reply
    assert "游侠" in result.reply


@pytest.mark.anyio
@pytest.mark.parametrize("npc_id", ["ryan", "shir", "grey"])
async def test_mock_uses_profile_without_inventing_a_past_identity(npc_id):
    profile = PlayerProfileChatContext(
        display_name="洛恩",
        adventurer_class="ranger",
        class_title="游侠",
    )

    result = await MockChatProvider().generate_reply(
        _request(npc_id, "我是谁", player_profile=profile)
    )

    assert "洛恩" in result.reply
    assert "游侠" in result.reply
    assert "失去记忆" in result.reply
    assert any(
        boundary in result.reply for boundary in ("不认识", "不会", "无法证明")
    )


@pytest.mark.anyio
async def test_mock_keeps_the_traveler_address_without_a_profile():
    result = await MockChatProvider().generate_reply(_request("ryan", "你好"))

    assert "旅行者" in result.reply


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
async def test_mock_reads_quest_objective_without_mutating_context_or_commanding():
    quest_context = PlayerQuestChatContext(
        player_id="player-1",
        location_id="tavern",
        location_name="星辉酒馆",
        quest_id="missing-child",
        quest_status="accepted",
        quest_objective="去曦谷城堡向 Grey 询问失踪孩子的线索",
    )
    provider = MockChatProvider()
    requests = [
        _request(
            npc_id,
            "这个任务下一步做什么？",
            player_quest_context=quest_context,
        )
        for npc_id in ("ryan", "shir", "grey")
    ]

    results = [await provider.generate_reply(request) for request in requests]

    assert len({result.reply for result in results}) == 3
    assert all(quest_context.quest_objective in result.reply for result in results)
    assert all(request.player_quest_context is quest_context for request in requests)
    assert all(not hasattr(result, "command") for result in results)


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
