from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_session
from backend.app.database.agent_run_repository import AgentRunRepository, AgentRunNotFoundError, AgentRunPersistenceError
from backend.app.schemas.agent_run import AgentRunSummary, AgentRunDetail, ActionProposalInfo, DomainEventInfo, AgentTraceInfo
from backend.app.schemas.common import ApiResponse, ErrorResponse


router = APIRouter()


@router.get("/api/agent-runs/{run_id}", response_model=ApiResponse[AgentRunDetail], responses={404:{"model":ErrorResponse},503:{"model":ErrorResponse}})
def get_agent_run(run_id: UUID, session: Session = Depends(get_session)):
    try:
        detail = AgentRunRepository(session).get_detail(str(run_id))
    except AgentRunNotFoundError:
        return JSONResponse(status_code=404, content=ErrorResponse(message="agent run not found").model_dump())
    except AgentRunPersistenceError:
        return JSONResponse(status_code=503, content=ErrorResponse(message="agent run is unavailable").model_dump())
    return ApiResponse(data=AgentRunDetail(
        run=AgentRunSummary.model_validate(detail.run),
        proposals=[ActionProposalInfo.model_validate(p) for p in detail.proposals],
        events=[DomainEventInfo.model_validate(e) for e in detail.events],
        trace=[AgentTraceInfo.model_validate(t) for t in detail.trace],
    ))
