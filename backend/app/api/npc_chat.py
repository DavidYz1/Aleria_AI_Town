from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.app.api.dependencies import (
    get_app_settings,
    get_chat_provider,
    get_session,
)
from backend.app.core.config import Settings
from backend.app.database.chat_repository import (
    ChatRepository,
    ConversationNotFoundError,
)
from backend.app.database.npc_repository import NpcNotFoundError, NpcRepository
from backend.app.llm.provider import ChatProvider
from backend.app.schemas.chat import NpcChatData, NpcChatRequest
from backend.app.schemas.common import ApiResponse, ErrorResponse
from backend.app.services.chat_context import ChatContextAssembler, PromptLoader
from backend.app.services.chat_service import (
    ChatContextUnavailableError,
    ChatService,
    ChatServiceUnavailableError,
)


router = APIRouter()


@router.post(
    "/api/npcs/{npc_id}/chat",
    response_model=ApiResponse[NpcChatData],
    responses={
        404: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
async def chat_with_npc(
    npc_id: str,
    request: NpcChatRequest,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
    provider: ChatProvider = Depends(get_chat_provider),
):
    chat_repository = ChatRepository(session)
    service = ChatService(
        repository=chat_repository,
        context_assembler=ChatContextAssembler(
            NpcRepository(session),
            chat_repository,
            PromptLoader(),
        ),
        provider=provider,
        history_limit=settings.chat_history_limit,
        prompt_version=settings.chat_prompt_version,
    )

    try:
        result = await service.chat(npc_id=npc_id, request=request)
    except (NpcNotFoundError, ConversationNotFoundError) as exc:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(message=str(exc)).model_dump(),
        )
    except (ChatContextUnavailableError, ChatServiceUnavailableError) as exc:
        return JSONResponse(
            status_code=503,
            content=ErrorResponse(message=str(exc)).model_dump(),
        )

    return ApiResponse(data=result)
