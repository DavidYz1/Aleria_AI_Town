from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.app.agents.memory_retrieval import MemoryRetriever
from backend.app.api.dependencies import (
    get_cognition_service,
    get_embedding_provider,
    get_session,
)
from backend.app.database.npc_repository import (
    NpcDetailUnavailableError,
    NpcNotFoundError,
    NpcRepository,
)
from backend.app.database.player_quest_repository import PlayerQuestRepository
from backend.app.llm.embedding_provider import EmbeddingProvider
from backend.app.quests.missing_child import MissingChildQuestPolicy
from backend.app.schemas.common import ApiResponse, ErrorResponse
from backend.app.schemas.npc import NpcDetailData, NpcMemoryExplanationsData
from backend.app.services.cognition_projection import CognitionProjectionService
from backend.app.services.memory_explanation import (
    MemoryExplanationService,
    MemoryExplanationUnavailableError,
)
from backend.app.services.npc_service import NpcService
from backend.app.services.player_quest_context import PlayerQuestChatContextReader


router = APIRouter()


@router.get(
    "/api/npcs/{npc_id}",
    response_model=ApiResponse[NpcDetailData],
    responses={
        404: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def get_npc_detail(
    npc_id: str,
    session: Session = Depends(get_session),
):
    service = NpcService(NpcRepository(session))
    try:
        detail = service.get_detail(npc_id)
    except NpcNotFoundError as exc:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(message=str(exc)).model_dump(),
        )
    except NpcDetailUnavailableError as exc:
        return JSONResponse(
            status_code=503,
            content=ErrorResponse(message=str(exc)).model_dump(),
        )

    return ApiResponse(data=detail)


@router.get(
    "/api/npcs/{npc_id}/memory-explanations",
    response_model=ApiResponse[NpcMemoryExplanationsData],
    responses={
        404: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def get_npc_memory_explanations(
    npc_id: str,
    session: Session = Depends(get_session),
    cognition: CognitionProjectionService = Depends(get_cognition_service),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
):
    # Authoritative reads keep the request Session; cognition reads own the
    # separate Session the retriever requires to be free of open transactions.
    service = MemoryExplanationService(
        NpcRepository(session),
        MemoryRetriever(cognition.repository, embedding_provider),
        cognition=cognition,
        quest_context_reader=PlayerQuestChatContextReader(
            PlayerQuestRepository(session),
            MissingChildQuestPolicy(),
        ),
    )
    try:
        explanations = service.get_explanations(npc_id)
    except NpcNotFoundError as exc:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(message=str(exc)).model_dump(),
        )
    except MemoryExplanationUnavailableError as exc:
        return JSONResponse(
            status_code=503,
            content=ErrorResponse(message=str(exc)).model_dump(),
        )

    return ApiResponse(data=explanations)
