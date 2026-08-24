from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_session
from backend.app.database.player_quest_repository import (
    LocationNotFoundError,
    PlayerNotFoundError,
    PlayerQuestPersistenceError,
    PlayerQuestRepository,
    QuestNotFoundError,
)
from backend.app.quests.missing_child import MissingChildQuestPolicy
from backend.app.schemas.common import ApiResponse, ErrorResponse
from backend.app.schemas.player import PlayerTravelRequest
from backend.app.schemas.quest import PlayerQuestData
from backend.app.services.player_quest_service import (
    PlayerQuestService,
    PlayerQuestServiceUnavailableError,
)


router = APIRouter()


def _service(session: Session) -> PlayerQuestService:
    return PlayerQuestService(
        PlayerQuestRepository(session),
        MissingChildQuestPolicy(),
    )


@router.get(
    "/api/player",
    response_model=ApiResponse[PlayerQuestData],
    responses={
        404: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def get_player(session: Session = Depends(get_session)):
    try:
        data = _service(session).get_state()
    except (PlayerNotFoundError, QuestNotFoundError) as exc:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(message=str(exc)).model_dump(),
        )
    except (
        PlayerQuestPersistenceError,
        PlayerQuestServiceUnavailableError,
    ):
        return JSONResponse(
            status_code=503,
            content=ErrorResponse(
                message="Player quest service is unavailable"
            ).model_dump(),
        )
    return ApiResponse(data=data)


@router.post(
    "/api/player/travel",
    response_model=ApiResponse[PlayerQuestData],
    responses={
        404: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def travel_player(
    request: PlayerTravelRequest,
    session: Session = Depends(get_session),
):
    try:
        data = _service(session).travel(request)
    except (
        PlayerNotFoundError,
        QuestNotFoundError,
        LocationNotFoundError,
    ) as exc:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(message=str(exc)).model_dump(),
        )
    except (
        PlayerQuestPersistenceError,
        PlayerQuestServiceUnavailableError,
    ):
        return JSONResponse(
            status_code=503,
            content=ErrorResponse(
                message="Player quest service is unavailable"
            ).model_dump(),
        )
    return ApiResponse(data=data)
