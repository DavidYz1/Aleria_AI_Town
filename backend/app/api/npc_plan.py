from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_session
from backend.app.database.models import AgentPlan
from backend.app.database.npc_repository import (
    NpcDetailUnavailableError,
    NpcNotFoundError,
    NpcRepository,
)
from backend.app.database.plan_repository import PlanRepository
from backend.app.database.world_repository import CANONICAL_WORLD_ID
from backend.app.schemas.common import ApiResponse, ErrorResponse
from backend.app.schemas.plan import NpcPlanData, PlanInfo, PlanStepInfo


RECENT_PLAN_LIMIT = 5

router = APIRouter()


def _to_plan_info(plan: AgentPlan) -> PlanInfo:
    return PlanInfo(
        id=plan.id,
        goal=plan.goal,
        goal_reason=plan.goal_reason,
        thought=plan.thought,
        steps=[PlanStepInfo.model_validate(step) for step in plan.steps_json],
        current_step_index=plan.current_step_index,
        status=plan.status,
        created_clock_tick=plan.created_clock_tick,
        provider=plan.provider,
        model=plan.model,
        latency_ms=plan.latency_ms,
        tokens_used=plan.tokens_used,
    )


@router.get(
    "/api/npcs/{npc_id}/plan",
    response_model=ApiResponse[NpcPlanData],
    responses={
        404: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def get_npc_plan(
    npc_id: str,
    session: Session = Depends(get_session),
):
    try:
        NpcRepository(session).get_detail_records(npc_id)
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

    repository = PlanRepository(session)
    try:
        current = repository.get_active(CANONICAL_WORLD_ID, npc_id)
        recent = repository.recent(CANONICAL_WORLD_ID, npc_id, limit=RECENT_PLAN_LIMIT)
        data = NpcPlanData(
            current=None if current is None else _to_plan_info(current),
            recent=[_to_plan_info(plan) for plan in recent],
        )
    except (SQLAlchemyError, ValidationError):
        # 计划行由本服务写入，形状异常属于服务端故障；对外仍是有界的 503。
        return JSONResponse(
            status_code=503,
            content=ErrorResponse(message="npc plan is unavailable").model_dump(),
        )

    return ApiResponse(data=data)
