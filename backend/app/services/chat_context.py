from pathlib import Path
from datetime import UTC, datetime
import logging
from typing import Protocol

from backend.app.agents.memory_retrieval import MemoryRetriever, MemoryType, RetrievalRequest, RetrievalScope
from backend.app.services.cognition_projection import CognitionProjectionService

from backend.app.database.action_compat import to_public_action_type
from backend.app.database.chat_repository import (
    ChatPersistenceError,
    ChatRepository,
    ConversationNotFoundError,
)
from backend.app.database.npc_repository import (
    NpcActionRecord,
    NpcDetailUnavailableError,
    NpcNotFoundError,
    NpcRepository,
)
from backend.app.llm.types import (
    ChatActionContext,
    ChatHistoryMessage,
    ChatMemoryContext,
    ChatProviderRequest,
    PlayerProfileChatContext,
    PlayerQuestChatContext,
    PromptBundle,
)
from backend.app.world.clock import get_time_phase


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PROMPT_ROOT = REPO_ROOT / "prompts"
SUPPORTED_PROMPT_VERSIONS = {"v1", "v2", "v3"}
SUPPORTED_NPC_IDS = {"ryan", "shir", "grey"}


class PromptUnavailableError(RuntimeError):
    pass


class PlayerQuestContextReader(Protocol):
    def get_chat_context(self) -> PlayerQuestChatContext | None:
        raise NotImplementedError


class PromptLoader:
    def __init__(self, prompt_root: Path = DEFAULT_PROMPT_ROOT) -> None:
        self._prompt_root = prompt_root

    def load(self, *, version: str, npc_id: str) -> PromptBundle:
        if (
            version not in SUPPORTED_PROMPT_VERSIONS
            or npc_id not in SUPPORTED_NPC_IDS
        ):
            raise PromptUnavailableError("Chat context is unavailable")

        version_root = self._prompt_root / version
        paths = (
            version_root / "world_lore.md",
            version_root / "chat_system.md",
            version_root / "player_context.md",
            version_root / "characters" / f"{npc_id}.md",
        )
        try:
            contents = tuple(
                path.read_text(encoding="utf-8").strip() for path in paths
            )
        except (OSError, UnicodeError):
            raise PromptUnavailableError(
                "Chat context is unavailable"
            ) from None

        if any(not content for content in contents):
            raise PromptUnavailableError("Chat context is unavailable")

        return PromptBundle(
            world_lore=contents[0],
            chat_system_prompt=contents[1],
            player_context=contents[2],
            character_prompt=contents[3],
        )


class ChatContextAssembler:
    def __init__(
        self,
        npc_repository: NpcRepository,
        chat_repository: ChatRepository,
        prompt_loader: PromptLoader,
        player_quest_context_reader: PlayerQuestContextReader | None = None,
        memory_retriever: MemoryRetriever | None = None,
        cognition: CognitionProjectionService | None = None,
        memory_limit: int = 6,
        memory_char_budget: int = 1600,
    ) -> None:
        self._npc_repository = npc_repository
        self._chat_repository = chat_repository
        self._prompt_loader = prompt_loader
        self._player_quest_context_reader = player_quest_context_reader
        self._memory_retriever, self._cognition = memory_retriever, cognition
        self._memory_limit, self._memory_char_budget = memory_limit, memory_char_budget

    def assemble(
        self,
        *,
        npc_id: str,
        conversation_id: str | None,
        player_message: str,
        history_limit: int,
        prompt_version: str,
        player_profile: PlayerProfileChatContext | None = None,
    ) -> ChatProviderRequest:
        request_started_at = datetime.now(UTC)
        try:
            records = self._npc_repository.get_detail_records(npc_id)
            conversation_message_upper = self._chat_repository.get_committed_message_upper(
                npc_id=npc_id, world_id=records.world.id
            )
            prompts = self._prompt_loader.load(
                version=prompt_version,
                npc_id=npc_id,
            )
            stored_history = (
                ()
                if conversation_id is None
                else self._chat_repository.get_recent_messages(
                    conversation_id=conversation_id,
                    npc_id=npc_id,
                    world_id=records.world.id,
                    limit=history_limit,
                    upper_message_id=conversation_message_upper,
                )
            )
        except (NpcNotFoundError, ConversationNotFoundError):
            raise
        except (
            NpcDetailUnavailableError,
            ChatPersistenceError,
            PromptUnavailableError,
        ):
            raise PromptUnavailableError(
                "Chat context is unavailable"
            ) from None

        actions = tuple(
            ChatActionContext(
                clock_tick=action.clock_tick,
                world_time=action.world_time,
                action_type=action.action_type,
                target_name=self._target_name(records.target_names, action),
                reason_code=action.reason,
            )
            for action in records.actions
        )
        history = tuple(
            ChatHistoryMessage(role=message.role, content=message.content)
            for message in stored_history
        )

        quest_context = (None if self._player_quest_context_reader is None
            else self._player_quest_context_reader.get_chat_context())
        memories, retrieval_mode = (), "memory_unavailable"
        if self._cognition is not None:
            try:
                self._cognition.catch_up_owner(records.world.id, records.profile.id,
                    message_upper_bound=conversation_message_upper)
            except Exception:
                logging.getLogger(__name__).warning("Chat cognition unavailable category=core_projection")
        if self._memory_retriever is not None:
            try:
                result = self._memory_retriever.retrieve(RetrievalRequest(
                    world_id=records.world.id, owner_npc_id=records.profile.id,
                    current_world_version=records.world.world_version, current_clock_tick=records.world.clock_tick,
                    query_text=player_message, scope=RetrievalScope.PLAYER_DIALOGUE,
                    allowed_memory_types=frozenset(MemoryType), limit=self._memory_limit,
                    char_budget=self._memory_char_budget,
                    excluded_turn_ids=frozenset(message.turn_id for message in stored_history if message.turn_id),
                    conversation_message_upper=conversation_message_upper,
                    created_before=request_started_at))
                memories = tuple(ChatMemoryContext(item.memory_id, item.memory_type, item.source_label,
                    item.content, item.occurred_clock_tick, item.source_turn_id) for item in result.memories)
                retrieval_mode = result.mode
            except Exception:
                logging.getLogger(__name__).warning("Chat memory unavailable category=memory_unavailable")

        return ChatProviderRequest(
            npc_id=records.profile.id,
            npc_name=records.profile.name,
            role=records.profile.role,
            personality=tuple(records.profile.personality_json),
            character_prompt=prompts.character_prompt,
            world_lore=prompts.world_lore,
            chat_system_prompt=prompts.chat_system_prompt,
            player_context_prompt=prompts.player_context,
            world_id=records.world.id,
            world_name=records.world.name,
            world_day=records.world.day,
            world_version=records.world.world_version,
            world_time=records.world.time,
            clock_tick=records.world.clock_tick,
            time_phase=get_time_phase(records.world.time),
            location_id=records.state.location_id,
            location_name=records.location.name,
            current_action=to_public_action_type(records.state.current_action),
            energy=records.state.energy,
            mood=records.state.mood,
            social=records.state.social,
            recent_actions=actions,
            player_quest_context=quest_context,
            conversation_history=history,
            player_message=player_message,
            player_profile=player_profile,
            long_term_memories=memories,
            memory_retrieval_mode=retrieval_mode,
        )

    @staticmethod
    def _target_name(
        target_names: dict[tuple[str, str], str],
        action: NpcActionRecord,
    ) -> str | None:
        if action.target_kind is None or action.target_id is None:
            return None
        return target_names.get(
            (action.target_kind, action.target_id),
            action.target_id,
        )
