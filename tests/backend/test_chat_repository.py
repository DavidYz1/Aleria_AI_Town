from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
import pytest
from uuid import UUID

from backend.app.database.chat_repository import (
    ChatPersistenceError,
    ChatRepository,
    ConversationNotFoundError,
)
from backend.app.database.connection import create_engine_and_session
from backend.app.database.models import Conversation, ConversationMessage
from scripts.seed_world import seed_database


CONVERSATION_ID = "5e547c21-a228-4e86-940d-a1bf5d65702f"


@pytest.mark.parametrize("database_fixture", ["database_url", "postgres_database_url"])
def test_same_owner_turns_cannot_overtake_before_message_id_allocation(request, database_fixture, seed_dir):
    """Catch a later conversation allocating/committing IDs before an earlier owner transaction."""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event as Signal
    from sqlalchemy import event
    from backend.app.database.cognition_repository import CognitionRepository
    from backend.app.database.models import Memory
    from backend.app.services.cognition_projection import CognitionProjectionService

    url = request.getfixturevalue(database_fixture)
    seed_database(url, seed_dir)
    engine, factory = create_engine_and_session(url)
    first_at_source_flush, release_first, second_attempted, second_finished = (Signal() for _ in range(4))

    def persist_first():
        with factory() as session:
            def pause_before_source_flush(session, context, instances):
                if any(isinstance(row, Conversation) for row in session.new):
                    first_at_source_flush.set()
                    assert release_first.wait(10), "test did not release the first source transaction"
            event.listen(session, "before_flush", pause_before_source_flush)
            return _persist_turn(ChatRepository(session), create_conversation=True, turn_number=1)

    def persist_second():
        with factory() as session:
            # Observe the real second connection attempting its first SQL write.
            connection = session.connection()
            def attempted(connection, cursor, statement, parameters, context, executemany):
                if statement.lstrip().upper().startswith(("UPDATE", "INSERT")):
                    second_attempted.set()
            event.listen(connection, "before_cursor_execute", attempted)
            try:
                return _persist_turn(ChatRepository(session), conversation_id=str(UUID(int=2)),
                                     create_conversation=True, turn_number=2)
            finally:
                second_finished.set()

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(persist_first)
            try:
                assert first_at_source_flush.wait(5)
                second = pool.submit(persist_second)
                assert second_attempted.wait(5)
                overtook = second_finished.wait(0.5)
            finally:
                release_first.set()
            first_turn, second_turn = first.result(timeout=10), second.result(timeout=10)
        assert not overtook, "same-owner source transaction overtook the first before its commit"
        assert (first_turn.user.id, first_turn.assistant.id, second_turn.user.id, second_turn.assistant.id) == (1, 2, 3, 4)
        with factory() as session:
            result = CognitionProjectionService(CognitionRepository(session)).catch_up_owner("aleria-town", "ryan")
            assert result.created_memories == 2
            assert session.scalar(select(func.count()).select_from(Memory).where(Memory.memory_type == "conversation")) == 2
    finally:
        engine.dispose()


def _persist_turn(
    repository: ChatRepository,
    *,
    conversation_id: str = CONVERSATION_ID,
    create_conversation: bool,
    turn_number: int,
):
    turn_id = str(UUID(int=turn_number))
    return repository.persist_turn(
        conversation_id=conversation_id,
        create_conversation=create_conversation,
        npc_id="ryan",
        world_id="aleria-town",
        clock_tick=turn_number - 1,
        turn_id=turn_id,
        world_version=0,
        world_time="08:00",
        user_content=f"user-{turn_number}",
        assistant_content=f"assistant-{turn_number}",
        emotion="guarded",
        provider="mock",
        fallback_used=False,
        prompt_version="v1",
    )


def test_internal_history_records_preserve_turn_ids_for_memory_deduplication(database_url, seed_dir):
    seed_database(database_url, seed_dir)
    engine, factory = create_engine_and_session(database_url)
    try:
        with factory() as session:
            repository = ChatRepository(session)
            turn = _persist_turn(repository, create_conversation=True, turn_number=1)
            assert turn.user.turn_id == turn.assistant.turn_id == str(UUID(int=1))
            history = repository.get_recent_messages(conversation_id=CONVERSATION_ID, npc_id="ryan", world_id="aleria-town", limit=2)
            assert [message.turn_id for message in history] == [str(UUID(int=1)), str(UUID(int=1))]
    finally:
        engine.dispose()


def test_repository_persists_a_new_complete_turn(database_url, seed_dir):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)

    with session_factory() as session:
        turn = _persist_turn(
            ChatRepository(session),
            create_conversation=True,
            turn_number=1,
        )

        conversation = session.get(Conversation, CONVERSATION_ID)
        messages = tuple(
            session.scalars(
                select(ConversationMessage).order_by(ConversationMessage.id)
            )
        )

    assert conversation is not None
    assert conversation.world_id == "aleria-town"
    assert conversation.npc_id == "ryan"
    assert conversation.created_clock_tick == 0
    assert conversation.created_at == conversation.updated_at
    assert turn.user.id == 1
    assert turn.user.role == "user"
    assert turn.user.content == "user-1"
    assert turn.user.emotion is None
    assert turn.assistant.id == 2
    assert turn.assistant.role == "assistant"
    assert turn.assistant.content == "assistant-1"
    assert turn.assistant.emotion == "guarded"
    assert [message.role for message in messages] == ["user", "assistant"]
    assert messages[0].provider is None
    assert messages[0].prompt_version is None
    assert messages[1].provider == "mock"
    assert messages[1].fallback_used == 0
    assert messages[1].prompt_version == "v1"
    assert messages[0].turn_id == messages[1].turn_id == str(UUID(int=1))
    assert (messages[0].world_version, messages[0].world_time) == (0, "08:00")
    assert (messages[1].world_version, messages[1].world_time) == (0, "08:00")


def test_repository_returns_only_newest_messages_in_chronological_order(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        repository = ChatRepository(session)
        for turn_number in range(1, 7):
            _persist_turn(
                repository,
                create_conversation=turn_number == 1,
                turn_number=turn_number,
            )

        history = repository.get_recent_messages(
            conversation_id=CONVERSATION_ID,
            npc_id="ryan",
            world_id="aleria-town",
            limit=10,
        )

    assert [message.id for message in history] == list(range(3, 13))
    assert history[0].content == "user-2"
    assert history[-1].content == "assistant-6"


@pytest.mark.parametrize(
    ("conversation_id", "npc_id", "world_id"),
    [
        ("missing-conversation", "ryan", "aleria-town"),
        (CONVERSATION_ID, "shir", "aleria-town"),
        (CONVERSATION_ID, "ryan", "other-world"),
    ],
)
def test_repository_hides_missing_or_cross_boundary_conversations(
    database_url,
    seed_dir,
    conversation_id,
    npc_id,
    world_id,
):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        repository = ChatRepository(session)
        _persist_turn(
            repository,
            create_conversation=True,
            turn_number=1,
        )

        with pytest.raises(
            ConversationNotFoundError,
            match="^Conversation not found$",
        ):
            repository.get_recent_messages(
                conversation_id=conversation_id,
                npc_id=npc_id,
                world_id=world_id,
                limit=10,
            )


def test_repository_rejects_non_positive_history_limit(database_url, seed_dir):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        with pytest.raises(ValueError, match="history limit must be positive"):
            ChatRepository(session).get_recent_messages(
                conversation_id=CONVERSATION_ID,
                npc_id="ryan",
                world_id="aleria-town",
                limit=0,
            )


def test_repository_rolls_back_every_row_when_new_turn_commit_fails(
    database_url,
    seed_dir,
    monkeypatch,
):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        def fail_commit():
            raise SQLAlchemyError("forced commit failure")

        monkeypatch.setattr(session, "commit", fail_commit)
        with pytest.raises(
            ChatPersistenceError,
            match="^Chat service is unavailable$",
        ):
            _persist_turn(
                ChatRepository(session),
                create_conversation=True,
                turn_number=1,
            )

    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Conversation)) == 0
        assert (
            session.scalar(
                select(func.count()).select_from(ConversationMessage)
            )
            == 0
        )


def test_repository_rolls_back_existing_conversation_update_on_commit_failure(
    database_url,
    seed_dir,
    monkeypatch,
):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        repository = ChatRepository(session)
        _persist_turn(
            repository,
            create_conversation=True,
            turn_number=1,
        )
        before = session.get(Conversation, CONVERSATION_ID)
        assert before is not None
        original_updated_at = before.updated_at

        def fail_commit():
            raise SQLAlchemyError("forced commit failure")

        monkeypatch.setattr(session, "commit", fail_commit)
        with pytest.raises(ChatPersistenceError):
            _persist_turn(
                repository,
                create_conversation=False,
                turn_number=2,
            )

    with session_factory() as session:
        conversation = session.get(Conversation, CONVERSATION_ID)
        message_count = session.scalar(
            select(func.count()).select_from(ConversationMessage)
        )

    assert conversation is not None
    assert conversation.updated_at == original_updated_at
    assert message_count == 2
