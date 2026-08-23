from datetime import UTC, datetime

import pytest
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError

from backend.app.database.connection import create_engine_and_session
from backend.app.database.models import (
    Base,
    Conversation,
    ConversationMessage,
)
from scripts.seed_world import seed_database
from scripts.upgrade_schema import upgrade_schema


CONVERSATION_ID = "5e547c21-a228-4e86-940d-a1bf5d65702f"


def _conversation(conversation_id: str = CONVERSATION_ID) -> Conversation:
    now = datetime.now(UTC)
    return Conversation(
        id=conversation_id,
        world_id="aleria-town",
        npc_id="ryan",
        created_tick=0,
        created_at=now,
        updated_at=now,
    )


def test_upgrade_schema_creates_chat_tables_and_indexes(database_url):
    upgrade_schema(database_url)
    engine, _ = create_engine_and_session(database_url)
    inspector = inspect(engine)

    assert {"conversations", "conversation_messages"} <= set(
        inspector.get_table_names()
    )
    assert "ix_conversations_npc_updated" in {
        index["name"] for index in inspector.get_indexes("conversations")
    }
    assert "ix_conversation_messages_conversation_id_id" in {
        index["name"]
        for index in inspector.get_indexes("conversation_messages")
    }


def test_chat_models_store_one_complete_turn(database_url, seed_dir):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    now = datetime.now(UTC)

    with session_factory() as session:
        session.add(_conversation())
        session.add_all(
            [
                ConversationMessage(
                    conversation_id=CONVERSATION_ID,
                    role="user",
                    content="你害怕史莱姆吗？",
                    emotion=None,
                    provider=None,
                    fallback_used=0,
                    prompt_version=None,
                    world_tick=0,
                    created_at=now,
                ),
                ConversationMessage(
                    conversation_id=CONVERSATION_ID,
                    role="assistant",
                    content="害怕？当然不是……",
                    emotion="guarded",
                    provider="mock",
                    fallback_used=0,
                    prompt_version="v1",
                    world_tick=0,
                    created_at=now,
                ),
            ]
        )
        session.commit()

        messages = tuple(
            session.scalars(
                select(ConversationMessage).order_by(ConversationMessage.id)
            )
        )

    assert [message.id for message in messages] == [1, 2]
    assert messages[0].role == "user"
    assert messages[0].emotion is None
    assert messages[0].provider is None
    assert messages[0].prompt_version is None
    assert messages[0].fallback_used == 0
    assert messages[1].role == "assistant"
    assert messages[1].emotion == "guarded"
    assert messages[1].provider == "mock"
    assert messages[1].prompt_version == "v1"


def test_conversation_rejects_negative_created_tick(database_url, seed_dir):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)

    with session_factory() as session:
        conversation = _conversation()
        conversation.created_tick = -1
        session.add(conversation)
        with pytest.raises(IntegrityError):
            session.commit()


def test_conversation_rejects_unknown_world_or_npc(database_url, seed_dir):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)

    with session_factory() as session:
        conversation = _conversation()
        conversation.world_id = "missing-world"
        conversation.npc_id = "missing-npc"
        session.add(conversation)
        with pytest.raises(IntegrityError):
            session.commit()


@pytest.mark.parametrize(
    ("role", "fallback_used", "world_tick"),
    [
        ("system", 0, 0),
        ("assistant", 2, 0),
        ("assistant", 0, -1),
    ],
)
def test_conversation_message_enforces_role_fallback_and_tick_constraints(
    database_url,
    seed_dir,
    role,
    fallback_used,
    world_tick,
):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    now = datetime.now(UTC)

    with session_factory() as session:
        session.add(_conversation())
        session.commit()
        session.add(
            ConversationMessage(
                conversation_id=CONVERSATION_ID,
                role=role,
                content="测试消息",
                emotion="neutral" if role == "assistant" else None,
                provider="mock" if role == "assistant" else None,
                fallback_used=fallback_used,
                prompt_version="v1" if role == "assistant" else None,
                world_tick=world_tick,
                created_at=now,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_conversation_message_requires_existing_conversation(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)

    with session_factory() as session:
        session.add(
            ConversationMessage(
                conversation_id="missing-conversation",
                role="user",
                content="测试消息",
                emotion=None,
                provider=None,
                fallback_used=0,
                prompt_version=None,
                world_tick=0,
                created_at=datetime.now(UTC),
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()

        session.rollback()
        assert (
            session.scalar(
                select(func.count()).select_from(ConversationMessage)
            )
            == 0
        )
