from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_session
from backend.app.database.player_quest_repository import (
    PlayerNotFoundError,
    PlayerQuestPersistenceError,
    PlayerQuestRepository,
    QuestNotFoundError,
)
from backend.app.quests.missing_child import MissingChildQuestPolicy
from backend.app.quests.types import (
    QuestInteractionUnavailableError,
    QuestStateConflictError,
)
from backend.app.schemas.common import ApiResponse, ErrorResponse
from backend.app.schemas.quest import (
    PlayerQuestData,
    QuestInteractRequest,
)
from backend.app.services.player_quest_service import (
    PlayerQuestService,
    PlayerQuestServiceUnavailableError,
)


router = APIRouter()


@router.post(
    "/api/quests/missing-child/interact",
    response_model=ApiResponse[PlayerQuestData],
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def interact_with_missing_child_quest(
    request: QuestInteractRequest,
    session: Session = Depends(get_session),
):
    service = PlayerQuestService(
        PlayerQuestRepository(session),
        MissingChildQuestPolicy(),
    )
    try:
        data = service.interact(request)
    except (PlayerNotFoundError, QuestNotFoundError) as exc:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(message=str(exc)).model_dump(),
        )
    except (
        QuestStateConflictError,
        QuestInteractionUnavailableError,
    ) as exc:
        return JSONResponse(
            status_code=409,
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
