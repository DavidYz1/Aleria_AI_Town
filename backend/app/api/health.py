from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_chat_provider, get_session
from backend.app.llm.provider import ChatProvider
from backend.app.schemas.common import ApiResponse, ErrorResponse
from backend.app.schemas.health import HealthData


router = APIRouter()


@router.get(
    "/api/health",
    response_model=ApiResponse[HealthData],
    responses={503: {"model": ErrorResponse}},
)
def get_health(
    session: Session = Depends(get_session),
    chat_provider: ChatProvider = Depends(get_chat_provider),
):
    try:
        session.execute(text("SELECT 1")).scalar_one()
    except SQLAlchemyError:
        error = ErrorResponse(message="database is unavailable")
        return JSONResponse(status_code=503, content=error.model_dump())

    return ApiResponse(
        data=HealthData(chat_provider=chat_provider.name),
    )
