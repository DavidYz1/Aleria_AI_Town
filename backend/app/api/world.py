from collections.abc import Generator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.app.database.world_repository import (
    WorldRepository,
    WorldUnavailableError,
)
from backend.app.schemas.common import ApiResponse, ErrorResponse
from backend.app.schemas.world import WorldData
from backend.app.services.world_service import WorldService


router = APIRouter()


def get_session(request: Request) -> Generator[Session, None, None]:
    with request.app.state.session_factory() as session:
        yield session


@router.get(
    "/api/world",
    response_model=ApiResponse[WorldData],
    responses={503: {"model": ErrorResponse}},
)
def get_world(session: Session = Depends(get_session)):
    service = WorldService(WorldRepository(session))
    try:
        world = service.get_world()
    except WorldUnavailableError as exc:
        error = ErrorResponse(message=str(exc))
        return JSONResponse(status_code=503, content=error.model_dump())

    return ApiResponse(data=world)
