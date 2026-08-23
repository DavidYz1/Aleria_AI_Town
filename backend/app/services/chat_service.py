from uuid import UUID, uuid4

from backend.app.database.chat_repository import (
    ChatPersistenceError,
    ChatRepository,
)
from backend.app.llm.provider import ChatProvider, ChatProviderError
from backend.app.schemas.chat import (
    ChatAssistantMessageData,
    ChatTurnData,
    ChatUserMessageData,
    NpcChatData,
    NpcChatRequest,
)
from backend.app.services.chat_context import (
    ChatContextAssembler,
    PromptUnavailableError,
)


class ChatContextUnavailableError(RuntimeError):
    pass


class ChatServiceUnavailableError(RuntimeError):
    pass


class ChatService:
    def __init__(
        self,
        *,
        repository: ChatRepository,
        context_assembler: ChatContextAssembler,
        provider: ChatProvider,
        history_limit: int,
        prompt_version: str,
    ) -> None:
        self._repository = repository
        self._context_assembler = context_assembler
        self._provider = provider
        self._history_limit = history_limit
        self._prompt_version = prompt_version

    async def chat(
        self,
        *,
        npc_id: str,
        request: NpcChatRequest,
    ) -> NpcChatData:
        create_conversation = request.conversation_id is None
        conversation_id = str(request.conversation_id or uuid4())

        try:
            context = self._context_assembler.assemble(
                npc_id=npc_id,
                conversation_id=(
                    None if create_conversation else conversation_id
                ),
                player_message=request.message,
                history_limit=self._history_limit,
                prompt_version=self._prompt_version,
            )
        except PromptUnavailableError:
            raise ChatContextUnavailableError(
                "Chat context is unavailable"
            ) from None

        try:
            provider_result = await self._provider.generate_reply(context)
        except ChatProviderError:
            raise ChatServiceUnavailableError(
                "Chat service is unavailable"
            ) from None

        try:
            persisted = self._repository.persist_turn(
                conversation_id=conversation_id,
                create_conversation=create_conversation,
                npc_id=context.npc_id,
                world_id=context.world_id,
                world_tick=context.world_tick,
                user_content=request.message,
                assistant_content=provider_result.reply,
                emotion=provider_result.emotion,
                provider=provider_result.provider,
                fallback_used=provider_result.fallback_used,
                prompt_version=self._prompt_version,
            )
        except ChatPersistenceError:
            raise ChatServiceUnavailableError(
                "Chat service is unavailable"
            ) from None

        return NpcChatData(
            conversation_id=UUID(conversation_id),
            npc_id=context.npc_id,
            turn=ChatTurnData(
                user=ChatUserMessageData(
                    id=persisted.user.id,
                    content=persisted.user.content,
                ),
                assistant=ChatAssistantMessageData(
                    id=persisted.assistant.id,
                    content=persisted.assistant.content,
                    emotion=persisted.assistant.emotion,
                ),
            ),
            provider=provider_result.provider,
            fallback_used=provider_result.fallback_used,
        )
