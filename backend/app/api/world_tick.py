from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.app.api.world import get_session
from backend.app.database.world_repository import WorldUnavailableError
from backend.app.database.world_tick_repository import (
    WorldTickConflictError,
    WorldTickPersistenceError,
    WorldTickRepository,
)
from backend.app.schemas.common import ApiResponse, ErrorResponse
from backend.app.schemas.world_tick import WorldTickData, WorldTickRequest
from backend.app.services.world_tick_service import WorldTickService


router = APIRouter()


@router.post(
    "/api/world/tick",
    response_model=ApiResponse[WorldTickData],
    responses={
        409: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def advance_world_tick(
    request: WorldTickRequest,
    session: Session = Depends(get_session),
):
    service = WorldTickService(WorldTickRepository(session))
    try:
        data = service.advance(request.expected_tick)
    except WorldTickConflictError as exc:
        return JSONResponse(
            status_code=409,
            content=ErrorResponse(message=str(exc)).model_dump(),
        )
    except (WorldUnavailableError, WorldTickPersistenceError) as exc:
        message = (
            str(exc)
            if isinstance(exc, WorldUnavailableError)
            else "world state is unavailable"
        )
        return JSONResponse(
            status_code=503,
            content=ErrorResponse(message=message).model_dump(),
        )

    return ApiResponse(data=data)
