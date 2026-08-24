import importlib

from sqlalchemy import func, select
import pytest

from backend.app.database.chat_repository import ChatRepository
from backend.app.database.connection import create_engine_and_session
from backend.app.database.models import (
    Conversation,
    ConversationMessage,
    Event,
    NpcState,
    PlayerState,
    QuestEvent,
    QuestProgress,
    WorldAction,
    WorldState,
)
from backend.app.database.npc_repository import NpcNotFoundError, NpcRepository
from backend.app.llm.provider import ChatProviderError, ChatProviderResult
from backend.app.llm.types import PlayerProfileChatContext
from backend.app.schemas.chat import NpcChatRequest
from backend.app.services.chat_context import ChatContextAssembler, PromptLoader
from backend.app.services.chat_service import (
    ChatContextUnavailableError,
    ChatService,
    ChatServiceUnavailableError,
)
from scripts.seed_world import seed_database


class _CapturingProvider:
    name = "test-provider"

    def __init__(
        self,
        *,
        error: Exception | None = None,
        fallback_used: bool = False,
    ) -> None:
        self.error = error
        self.fallback_used = fallback_used
        self.requests = []

    async def generate_reply(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return ChatProviderResult(
            reply=f"{request.npc_name} 回复：{request.player_message}",
            emotion="cheerful",
            provider=self.name,
            fallback_used=self.fallback_used,
        )


def _service(
    session,
    provider,
    *,
    prompt_loader=None,
    player_quest_context_reader=None,
) -> ChatService:
    chat_repository = ChatRepository(session)
    return ChatService(
        repository=chat_repository,
        context_assembler=ChatContextAssembler(
            NpcRepository(session),
            chat_repository,
            prompt_loader or PromptLoader(),
            player_quest_context_reader=player_quest_context_reader,
        ),
        provider=provider,
        history_limit=10,
        prompt_version="v1",
    )


def _game_snapshot(session):
    return {
        "world": tuple(
            session.execute(
                select(
                    WorldState.id,
                    WorldState.name,
                    WorldState.day,
                    WorldState.time,
                    WorldState.tick,
                ).order_by(WorldState.id)
            ).all()
        ),
        "players": tuple(
            session.execute(
                select(
                    PlayerState.id,
                    PlayerState.location_id,
                ).order_by(PlayerState.id)
            ).all()
        ),
        "npcs": tuple(
            session.execute(
                select(
                    NpcState.npc_id,
                    NpcState.location_id,
                    NpcState.current_action,
                    NpcState.energy,
                    NpcState.mood,
                    NpcState.social,
                ).order_by(NpcState.npc_id)
            ).all()
        ),
        "quests": tuple(
            session.execute(
                select(
                    QuestProgress.player_id,
                    QuestProgress.quest_id,
                    QuestProgress.status,
                    QuestProgress.version,
                    QuestProgress.updated_tick,
                ).order_by(
                    QuestProgress.player_id,
                    QuestProgress.quest_id,
                )
            ).all()
        ),
        "world_actions": session.scalar(
            select(func.count()).select_from(WorldAction)
        ),
        "events": session.scalar(select(func.count()).select_from(Event)),
        "quest_events": session.scalar(
            select(func.count()).select_from(QuestEvent)
        ),
    }


@pytest.mark.anyio
async def test_service_creates_and_persists_a_complete_chat_turn(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    provider = _CapturingProvider(fallback_used=True)

    with session_factory() as session:
        result = await _service(session, provider).chat(
            npc_id="ryan",
            request=NpcChatRequest(message="你好，Ryan。"),
        )

        conversation = session.get(Conversation, str(result.conversation_id))
        messages = tuple(
            session.scalars(
                select(ConversationMessage).order_by(ConversationMessage.id)
            )
        )

    assert conversation is not None
    assert conversation.npc_id == "ryan"
    assert result.npc_id == "ryan"
    assert result.turn.user.id == messages[0].id
    assert result.turn.user.content == "你好，Ryan。"
    assert result.turn.assistant.id == messages[1].id
    assert result.turn.assistant.content == "Ryan 回复：你好，Ryan。"
    assert result.turn.assistant.emotion == "cheerful"
    assert result.provider == "test-provider"
    assert result.fallback_used is True
    assert messages[1].provider == "test-provider"
    assert messages[1].fallback_used == 1
    assert messages[1].prompt_version == "v1"


@pytest.mark.anyio
async def test_service_reuses_conversation_and_supplies_prior_turn_as_history(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    provider = _CapturingProvider()

    with session_factory() as session:
        service = _service(session, provider)
        first = await service.chat(
            npc_id="shir",
            request=NpcChatRequest(message="第一句"),
        )
        second = await service.chat(
            npc_id="shir",
            request=NpcChatRequest(
                conversation_id=first.conversation_id,
                message="第二句",
            ),
        )

        conversation_count = session.scalar(
            select(func.count()).select_from(Conversation)
        )
        message_count = session.scalar(
            select(func.count()).select_from(ConversationMessage)
        )

    assert second.conversation_id == first.conversation_id
    assert conversation_count == 1
    assert message_count == 4
    assert [item.content for item in provider.requests[1].conversation_history] == [
        "第一句",
        "Shir 回复：第一句",
    ]
    assert provider.requests[1].player_message == "第二句"


@pytest.mark.anyio
async def test_service_passes_player_profile_without_mutating_game_state(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    provider = _CapturingProvider()

    with session_factory() as session:
        before = _game_snapshot(session)
        result = await _service(session, provider).chat(
            npc_id="ryan",
            request=NpcChatRequest.model_validate(
                {
                    "message": "你认识我吗？",
                    "player_profile": {
                        "display_name": "洛恩",
                        "adventurer_class": "ranger",
                    },
                }
            ),
        )
        session.expire_all()
        after = _game_snapshot(session)
        messages = tuple(
            session.scalars(
                select(ConversationMessage).order_by(ConversationMessage.id)
            )
        )

    assert provider.requests[0].player_profile == PlayerProfileChatContext(
        display_name="洛恩",
        adventurer_class="ranger",
        class_title="游侠",
    )
    assert after == before
    assert result.turn.user.content == "你认识我吗？"
    assert [message.role for message in messages] == ["user", "assistant"]


@pytest.mark.anyio
async def test_service_does_not_persist_any_rows_when_provider_fails(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    provider = _CapturingProvider(
        error=ChatProviderError("upstream detail"),
    )

    with session_factory() as session:
        with pytest.raises(
            ChatServiceUnavailableError,
            match="^Chat service is unavailable$",
        ):
            await _service(session, provider).chat(
                npc_id="grey",
                request=NpcChatRequest(message="你好"),
            )

        assert session.scalar(
            select(func.count()).select_from(Conversation)
        ) == 0
        assert session.scalar(
            select(func.count()).select_from(ConversationMessage)
        ) == 0


@pytest.mark.anyio
async def test_service_maps_prompt_failure_to_context_unavailable(
    database_url,
    seed_dir,
    tmp_path,
):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)

    with session_factory() as session:
        with pytest.raises(
            ChatContextUnavailableError,
            match="^Chat context is unavailable$",
        ):
            await _service(
                session,
                _CapturingProvider(),
                prompt_loader=PromptLoader(tmp_path / "missing-prompts"),
            ).chat(
                npc_id="ryan",
                request=NpcChatRequest(message="你好"),
            )


@pytest.mark.anyio
async def test_service_preserves_npc_not_found(database_url, seed_dir):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)

    with session_factory() as session:
        with pytest.raises(NpcNotFoundError, match="^NPC not found$"):
            await _service(session, _CapturingProvider()).chat(
                npc_id="missing",
                request=NpcChatRequest(message="你好"),
            )


@pytest.mark.anyio
async def test_chat_does_not_modify_deterministic_world_state(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)

    with session_factory() as session:
        world = session.get(WorldState, "aleria-town")
        assert world is not None
        world_before = (world.id, world.name, world.day, world.time, world.tick)
        npc_before = tuple(
            (
                state.npc_id,
                state.location_id,
                state.current_action,
                state.energy,
                state.mood,
                state.social,
            )
            for state in session.scalars(
                select(NpcState).order_by(NpcState.npc_id)
            )
        )
        action_count_before = session.scalar(
            select(func.count()).select_from(WorldAction)
        )
        event_count_before = session.scalar(select(func.count()).select_from(Event))

        await _service(session, _CapturingProvider()).chat(
            npc_id="ryan",
            request=NpcChatRequest(message="你好"),
        )

        session.expire_all()
        world = session.get(WorldState, "aleria-town")
        assert world is not None
        world_after = (world.id, world.name, world.day, world.time, world.tick)
        npc_after = tuple(
            (
                state.npc_id,
                state.location_id,
                state.current_action,
                state.energy,
                state.mood,
                state.social,
            )
            for state in session.scalars(
                select(NpcState).order_by(NpcState.npc_id)
            )
        )
        action_count_after = session.scalar(
            select(func.count()).select_from(WorldAction)
        )
        event_count_after = session.scalar(select(func.count()).select_from(Event))

    assert world_after == world_before
    assert npc_after == npc_before
    assert action_count_after == action_count_before
    assert event_count_after == event_count_before


@pytest.mark.anyio
async def test_chat_reads_player_quest_context_without_mutating_it(
    database_url,
    seed_dir,
):
    try:
        reader_module = importlib.import_module(
            "backend.app.services.player_quest_context"
        )
    except ModuleNotFoundError:
        pytest.fail("player quest chat context reader is missing")

    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    provider = _CapturingProvider()
    with session_factory() as session:
        player = session.get(PlayerState, "default-player")
        progress = session.get(
            QuestProgress,
            ("default-player", "missing-child"),
        )
        assert player is not None
        assert progress is not None
        state_before = (
            player.location_id,
            progress.status,
            progress.version,
            session.scalar(select(func.count()).select_from(QuestEvent)),
        )

        await _service(
            session,
            provider,
            player_quest_context_reader=(
                reader_module.PlayerQuestChatContextReader(
                    reader_module.PlayerQuestRepository(session),
                    reader_module.MissingChildQuestPolicy(),
                )
            ),
        ).chat(
            npc_id="grey",
            request=NpcChatRequest(message="现在的任务是什么？"),
        )

        session.expire_all()
        player = session.get(PlayerState, "default-player")
        progress = session.get(
            QuestProgress,
            ("default-player", "missing-child"),
        )
        assert player is not None
        assert progress is not None
        state_after = (
            player.location_id,
            progress.status,
            progress.version,
            session.scalar(select(func.count()).select_from(QuestEvent)),
        )

    context = provider.requests[0].player_quest_context
    assert context is not None
    assert context.quest_objective == "查看星辉酒馆告示板上的失踪委托。"
    assert state_after == state_before
