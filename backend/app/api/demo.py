import json
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_session
from backend.app.schemas.common import ApiResponse, ErrorResponse
from backend.app.schemas.demo import DemoResetData
from backend.app.services.demo_reset_service import (
    DemoResetPersistenceError,
    DemoResetService,
    load_seed_data,
)


router = APIRouter()
DATA_DIR = Path(__file__).resolve().parents[3] / "data"


@router.post(
    "/api/demo/reset",
    response_model=ApiResponse[DemoResetData],
    responses={503: {"model": ErrorResponse}},
)
def reset_demo(session: Session = Depends(get_session)):
    try:
        data = DemoResetService(session).reset(load_seed_data(DATA_DIR))
    except (
        OSError,
        json.JSONDecodeError,
        ValidationError,
        DemoResetPersistenceError,
    ):
        return JSONResponse(
            status_code=503,
            content=ErrorResponse(
                message="Demo reset is unavailable"
            ).model_dump(),
        )

    return ApiResponse(data=data, message="Demo world reset")
