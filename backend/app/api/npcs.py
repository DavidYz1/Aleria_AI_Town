from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_session
from backend.app.database.npc_repository import (
    NpcDetailUnavailableError,
    NpcNotFoundError,
    NpcRepository,
)
from backend.app.schemas.common import ApiResponse, ErrorResponse
from backend.app.schemas.npc import NpcDetailData
from backend.app.services.npc_service import NpcService


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
