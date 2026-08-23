from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
import pytest

from backend.app.database.chat_repository import (
    ChatPersistenceError,
    ChatRepository,
    ConversationNotFoundError,
)
from backend.app.database.connection import create_engine_and_session
from backend.app.database.models import Conversation, ConversationMessage
from scripts.seed_world import seed_database


CONVERSATION_ID = "5e547c21-a228-4e86-940d-a1bf5d65702f"


def _persist_turn(
    repository: ChatRepository,
    *,
    conversation_id: str = CONVERSATION_ID,
    create_conversation: bool,
    turn_number: int,
):
    return repository.persist_turn(
        conversation_id=conversation_id,
        create_conversation=create_conversation,
        npc_id="ryan",
        world_id="aleria-town",
        world_tick=turn_number - 1,
        user_content=f"user-{turn_number}",
        assistant_content=f"assistant-{turn_number}",
        emotion="guarded",
        provider="mock",
        fallback_used=False,
        prompt_version="v1",
    )


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
    assert conversation.created_tick == 0
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
