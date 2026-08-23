from dataclasses import dataclass
from datetime import UTC, datetime
import logging
from typing import Literal, cast

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.database.models import Conversation, ConversationMessage


logger = logging.getLogger(__name__)


class ConversationNotFoundError(RuntimeError):
    pass


class ChatPersistenceError(RuntimeError):
    pass


@dataclass(frozen=True)
class ChatMessageRecord:
    id: int
    role: Literal["user", "assistant"]
    content: str
    emotion: str | None


@dataclass(frozen=True)
class PersistedChatTurn:
    user: ChatMessageRecord
    assistant: ChatMessageRecord


class ChatRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_recent_messages(
        self,
        *,
        conversation_id: str,
        npc_id: str,
        world_id: str,
        limit: int,
    ) -> tuple[ChatMessageRecord, ...]:
        if limit < 1:
            raise ValueError("history limit must be positive")

        try:
            self._require_conversation(
                conversation_id=conversation_id,
                npc_id=npc_id,
                world_id=world_id,
            )
            newest_first = tuple(
                self._session.scalars(
                    select(ConversationMessage)
                    .where(
                        ConversationMessage.conversation_id
                        == conversation_id
                    )
                    .order_by(ConversationMessage.id.desc())
                    .limit(limit)
                )
            )
        except ConversationNotFoundError:
            raise
        except SQLAlchemyError as exc:
            logger.exception("Failed to load chat history", exc_info=exc)
            raise ChatPersistenceError(
                "Chat service is unavailable"
            ) from None

        return tuple(
            self._to_record(message) for message in reversed(newest_first)
        )

    def persist_turn(
        self,
        *,
        conversation_id: str,
        create_conversation: bool,
        npc_id: str,
        world_id: str,
        world_tick: int,
        user_content: str,
        assistant_content: str,
        emotion: str,
        provider: str,
        fallback_used: bool,
        prompt_version: str,
    ) -> PersistedChatTurn:
        now = datetime.now(UTC)
        try:
            if create_conversation:
                conversation = Conversation(
                    id=conversation_id,
                    world_id=world_id,
                    npc_id=npc_id,
                    created_tick=world_tick,
                    created_at=now,
                    updated_at=now,
                )
                self._session.add(conversation)
                self._session.flush()
            else:
                conversation = self._require_conversation(
                    conversation_id=conversation_id,
                    npc_id=npc_id,
                    world_id=world_id,
                )

            user_message = ConversationMessage(
                conversation_id=conversation_id,
                role="user",
                content=user_content,
                emotion=None,
                provider=None,
                fallback_used=0,
                prompt_version=None,
                world_tick=world_tick,
                created_at=now,
            )
            assistant_message = ConversationMessage(
                conversation_id=conversation_id,
                role="assistant",
                content=assistant_content,
                emotion=emotion,
                provider=provider,
                fallback_used=int(fallback_used),
                prompt_version=prompt_version,
                world_tick=world_tick,
                created_at=now,
            )
            conversation.updated_at = now
            self._session.add_all([user_message, assistant_message])
            self._session.flush()
            persisted = PersistedChatTurn(
                user=self._to_record(user_message),
                assistant=self._to_record(assistant_message),
            )
            self._session.commit()
            return persisted
        except ConversationNotFoundError:
            raise
        except SQLAlchemyError as exc:
            self._session.rollback()
            logger.exception("Failed to persist chat turn", exc_info=exc)
            raise ChatPersistenceError(
                "Chat service is unavailable"
            ) from None

    def _require_conversation(
        self,
        *,
        conversation_id: str,
        npc_id: str,
        world_id: str,
    ) -> Conversation:
        conversation = self._session.get(Conversation, conversation_id)
        if (
            conversation is None
            or conversation.npc_id != npc_id
            or conversation.world_id != world_id
        ):
            raise ConversationNotFoundError("Conversation not found")
        return conversation

    @staticmethod
    def _to_record(message: ConversationMessage) -> ChatMessageRecord:
        return ChatMessageRecord(
            id=message.id,
            role=cast(Literal["user", "assistant"], message.role),
            content=message.content,
            emotion=message.emotion,
        )
