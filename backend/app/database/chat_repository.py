from dataclasses import dataclass
from datetime import UTC, datetime
import logging
from typing import Literal, cast

from sqlalchemy import func, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.database.models import Conversation, ConversationMessage, NpcProfile


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
    turn_id: str | None = None


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
        upper_message_id: int | None = None,
    ) -> tuple[ChatMessageRecord, ...]:
        if limit < 1:
            raise ValueError("history limit must be positive")

        try:
            self._require_conversation(
                conversation_id=conversation_id,
                npc_id=npc_id,
                world_id=world_id,
            )
            filters = [ConversationMessage.conversation_id == conversation_id]
            if upper_message_id is not None:
                filters.append(ConversationMessage.id <= upper_message_id)
            newest_first = tuple(
                self._session.scalars(
                    select(ConversationMessage)
                    .where(*filters)
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

    def get_committed_message_upper(self, *, npc_id: str, world_id: str) -> int:
        upper = self._session.scalar(
            select(func.max(ConversationMessage.id))
            .join(Conversation, Conversation.id == ConversationMessage.conversation_id)
            .where(Conversation.npc_id == npc_id, Conversation.world_id == world_id)
        )
        return int(upper or 0)

    def persist_turn(
        self,
        *,
        conversation_id: str,
        create_conversation: bool,
        npc_id: str,
        world_id: str,
        clock_tick: int,
        turn_id: str,
        world_version: int,
        world_time: str,
        user_content: str,
        assistant_content: str,
        emotion: str,
        provider: str,
        fallback_used: bool,
        prompt_version: str,
    ) -> PersistedChatTurn:
        now = datetime.now(UTC)
        try:
            # Serialize this owner's source transactions before any message IDs
            # are allocated. PostgreSQL sequences do not follow commit order;
            # the shared row lock makes the message checkpoint safe. The no-op
            # UPDATE also takes SQLite's write lock and changes no profile data.
            # This runs only during persistence, after provider work is complete.
            self._session.execute(
                update(NpcProfile)
                .where(NpcProfile.id == npc_id)
                .values(sort_order=NpcProfile.sort_order)
                .execution_options(synchronize_session=False)
            )
            if create_conversation:
                conversation = Conversation(
                    id=conversation_id,
                    world_id=world_id,
                    npc_id=npc_id,
                    created_clock_tick=clock_tick,
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
                clock_tick=clock_tick,
                turn_id=turn_id,
                world_version=world_version,
                world_time=world_time,
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
                clock_tick=clock_tick,
                turn_id=turn_id,
                world_version=world_version,
                world_time=world_time,
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
            turn_id=message.turn_id,
        )
