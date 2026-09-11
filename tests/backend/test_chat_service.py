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


@pytest.mark.anyio
@pytest.mark.parametrize("phase", ["pre", "post"])
async def test_slow_embedding_allows_another_chat_to_advance(database_url, seed_dir, phase):
    """Event handshake: the other Chat must reach its provider before HTTP is released."""
    import asyncio
    from threading import Event as Signal, Thread
    from backend.app.agents.memory_retrieval import MemoryRetriever
    from backend.app.database.cognition_repository import CognitionRepository
    from backend.app.llm.embedding_provider import DeterministicEmbeddingProvider
    from backend.app.services.cognition_projection import CognitionProjectionService, EmbeddingEnrichmentService
    seed_database(database_url, seed_dir)
    engine, factory = create_engine_and_session(database_url)
    entered, released, advanced = Signal(), Signal(), Signal()
    loop = asyncio.get_running_loop()
    fast_tasks, progress = [], []
    class BlockingEmbedding(DeterministicEmbeddingProvider):
        blocked = False
        def embed(self, text):
            if not self.blocked and (phase == "pre" or text == "slow claim"):
                self.blocked = True
                entered.set()
                assert released.wait(10), "test failed to release blocked embedding"
            return super().embed(text)
    class FastProvider(_CapturingProvider):
        async def generate_reply(self, request):
            advanced.set()
            return await super().generate_reply(request)
    async def fast_chat():
        with factory() as session:
            return await _service(session, FastProvider()).chat(npc_id="ryan", request=NpcChatRequest(message="fast claim"))
    def supervise():
        try:
            if not entered.wait(5):
                progress.append(False)
                return
            loop.call_soon_threadsafe(lambda: fast_tasks.append(asyncio.create_task(fast_chat())))
            # Timeout is a deadlock guard, not an arbitrary timing/sleep assertion.
            progress.append(advanced.wait(5))
        finally:
            released.set()
    supervisor = Thread(target=supervise, daemon=True)
    try:
        with factory() as session, factory() as cognition_session:
            repository = ChatRepository(session)
            cognition_repository = CognitionRepository(cognition_session)
            cognition = CognitionProjectionService(cognition_repository,
                enrichment=EmbeddingEnrichmentService(cognition_repository, BlockingEmbedding()))
            service = ChatService(repository=repository,
                context_assembler=ChatContextAssembler(NpcRepository(session), repository, PromptLoader(),
                    cognition=cognition, memory_retriever=MemoryRetriever(cognition_repository, DeterministicEmbeddingProvider())),
                provider=_CapturingProvider(), history_limit=2, prompt_version="v3", cognition=cognition)
            supervisor.start()
            slow = await service.chat(npc_id="grey", request=NpcChatRequest(message="slow claim"))
            await asyncio.to_thread(supervisor.join)
            fast = await asyncio.gather(*fast_tasks)
            assert entered.is_set() and progress == [True], "slow embedding blocked the Chat event loop"
            assert slow.turn.user.content == "slow claim"
            assert fast[0].turn.user.content == "fast claim"
            assert not cognition_session.in_transaction()
        with factory() as observer:
            assert observer.scalar(select(func.count()).select_from(ConversationMessage)) == 4
    finally:
        released.set()
        if supervisor.is_alive():
            await asyncio.to_thread(supervisor.join)
        engine.dispose()


@pytest.mark.anyio
@pytest.mark.parametrize("phase", ["pre", "post"])
async def test_cancelled_chat_waits_for_session_worker_before_request_cleanup(database_url, seed_dir, phase):
    import asyncio
    from threading import Event as Signal, Thread
    from backend.app.database.cognition_repository import CognitionRepository
    from backend.app.llm.embedding_provider import DeterministicEmbeddingProvider
    from backend.app.services.cognition_projection import CognitionProjectionService, EmbeddingEnrichmentService
    seed_database(database_url, seed_dir)
    engine, factory = create_engine_and_session(database_url)
    entered, released, loop_advanced, worker_finished = Signal(), Signal(), Signal(), Signal()
    loop = asyncio.get_running_loop()
    premature_cleanup = []
    class BlockingEmbedding(DeterministicEmbeddingProvider):
        def embed(self, text):
            if phase == "pre" or text == "cancelled claim":
                entered.set()
                assert released.wait(10)
            return super().embed(text)
    class ObservedAssembler(ChatContextAssembler):
        def assemble(self, **kwargs):
            try:
                return super().assemble(**kwargs)
            finally:
                if phase == "pre":
                    worker_finished.set()
    class ObservedCognition(CognitionProjectionService):
        def catch_up_owner(self, world_id, owner_npc_id):
            try:
                return super().catch_up_owner(world_id, owner_npc_id)
            finally:
                if phase == "post" and entered.is_set():
                    worker_finished.set()
    async def run_chat():
        with factory() as session, factory() as cognition_session:
            repository = ChatRepository(session)
            cognition_repository = CognitionRepository(cognition_session)
            cognition = ObservedCognition(cognition_repository,
                enrichment=EmbeddingEnrichmentService(cognition_repository, BlockingEmbedding()))
            try:
                return await ChatService(repository=repository,
                    context_assembler=ObservedAssembler(NpcRepository(session), repository, PromptLoader(), cognition=cognition),
                    provider=_CapturingProvider(), history_limit=2, prompt_version="v3", cognition=cognition).chat(
                        npc_id="grey", request=NpcChatRequest(message="cancelled claim"))
            finally:
                premature_cleanup.append(not worker_finished.is_set())
    task = asyncio.create_task(run_chat())
    def cancel_on_loop():
        task.cancel()
        loop.call_soon(loop_advanced.set)
    def supervise():
        try:
            assert entered.wait(5)
            loop.call_soon_threadsafe(cancel_on_loop)
            assert loop_advanced.wait(5)
        finally:
            released.set()
    supervisor = Thread(target=supervise, daemon=True)
    supervisor.start()
    try:
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.to_thread(supervisor.join)
        assert await asyncio.to_thread(worker_finished.wait, 10)
        assert premature_cleanup == [False], "request cleanup raced its session-owning worker"
        with factory() as observer:
            assert observer.scalar(select(func.count()).select_from(ConversationMessage)) == (0 if phase == "pre" else 2)
    finally:
        released.set()
        await asyncio.to_thread(supervisor.join)
        engine.dispose()


@pytest.mark.anyio
async def test_chat_post_commit_failure_preserves_complete_turn_and_later_compensates(database_url, seed_dir, caplog):
    # Catches projection before reply/commit, missing hooks, or a lost successful chat response.
    from backend.app.database.cognition_repository import CognitionRepository
    from backend.app.database.models import AgentCognitionState, Observation
    from backend.app.services.cognition_projection import CognitionProjectionService
    from tests.backend.test_cognition_projection import FailingCoreRepository

    seed_database(database_url, seed_dir)
    engine, factory = create_engine_and_session(database_url)
    class Provider(_CapturingProvider):
        async def generate_reply(self, request):
            with factory() as observer:
                assert observer.scalar(select(func.count()).select_from(Observation)) == 0
                assert observer.scalar(select(func.count()).select_from(ConversationMessage)) == 0
            return await super().generate_reply(request)
    with factory() as session, factory() as cognition_session:
        repository = ChatRepository(session)
        service = ChatService(repository=repository,
            context_assembler=ChatContextAssembler(NpcRepository(session), repository, PromptLoader()),
            provider=Provider(), history_limit=10, prompt_version="v1",
            cognition=CognitionProjectionService(FailingCoreRepository(cognition_session)))
        result = await service.chat(npc_id="grey", request=NpcChatRequest(message="A private claim"))
        assert result.npc_id == "grey" and result.turn.user.content == "A private claim"
        with factory() as observer:
            assert observer.scalar(select(func.count()).select_from(ConversationMessage)) == 2
            assert observer.scalar(select(func.count()).select_from(Observation)) == 0
            assert observer.scalar(select(func.count()).select_from(AgentCognitionState)) == 0
            world = observer.get(WorldState, "aleria-town")
            assert (world.world_version, world.clock_tick, world.event_sequence) == (0, 0, 0)
        assert any(getattr(record, "category", None) == "core_projection" for record in caplog.records)
        assert "sensitive injected secret" not in caplog.text
        assert CognitionProjectionService(CognitionRepository(cognition_session)).catch_up_owner("aleria-town", "grey").created_memories == 1
        assert session.get(AgentCognitionState, ("aleria-town", "ryan")) is None
    engine.dispose()


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
                    WorldState.clock_tick,
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
                    QuestProgress.updated_clock_tick,
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
    assert messages[0].turn_id == messages[1].turn_id
    assert messages[0].turn_id is not None
    assert (messages[0].world_version, messages[0].world_time) == (0, "08:00")
    assert (messages[1].world_version, messages[1].world_time) == (0, "08:00")
    assert provider.requests[0].world_version == 0


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
        world_before = (
            world.id,
            world.name,
            world.day,
            world.time,
            world.clock_tick,
        )
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
        world_after = (
            world.id,
            world.name,
            world.day,
            world.time,
            world.clock_tick,
        )
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
