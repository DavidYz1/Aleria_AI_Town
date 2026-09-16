from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.agents.memory_retrieval import (
    MemoryType,
    RetrievalRequest,
    RetrievalScope,
)
from backend.app.api.dependencies import get_session
from backend.app.database.cognition_repository import CognitionRepository
from backend.app.database.models import AgentPlan, WorldState
from backend.app.database.npc_repository import (
    NpcDetailUnavailableError,
    NpcNotFoundError,
    NpcRepository,
)
from backend.app.database.plan_repository import PlanRepository
from backend.app.database.world_repository import CANONICAL_WORLD_ID
from backend.app.schemas.common import ApiResponse, ErrorResponse
from backend.app.schemas.plan import (
    NpcPlanData,
    PlanEvidenceItem,
    PlanInfo,
    PlanStepInfo,
)
from backend.app.services.memory_explanation import (
    SOURCE_KINDS,
    SOURCE_LABELS,
    SUMMARY_MAX_LENGTH,
)


RECENT_PLAN_LIMIT = 5
# 检索用的内部标签 → 公开词汇。与 memory_explanation 用同一张表，
# 未知标签视为服务端错误，绝不臆造一个 kind。
MEMORY_TYPE_KINDS = {
    "episodic": "observed_event",
    "conversation": "player_claim",
    "knowledge": "authored_knowledge",
    "reflection": "reflection",
}

router = APIRouter()


def _public_evidence(session: Session, plan: AgentPlan) -> list[PlanEvidenceItem]:
    """把计划落盘的引用收窄成**玩家可见**的那一部分。

    落盘的 id 是完整的（planner 用 INTERNAL_REFLECTION 检索，含 secret 与
    internal_only），但这里必须重新过一遍公开硬过滤。不可公开的记忆既不出现内容，
    也不以计数或占位符暴露差额 —— 与 `memory-explanations` 同一条规则。

    `evidence_memory_ids_json is None` 表示这条计划早于 `0006`、没有这份记录，
    与「引用了 0 条」不同；两者在这里都返回空列表，但前者的成因写在模型注释里。
    """
    cited = plan.evidence_memory_ids_json
    if not cited:
        return []
    world = session.get(WorldState, plan.world_id)
    if world is None:
        return []
    request = RetrievalRequest(
        world_id=plan.world_id, owner_npc_id=plan.owner_npc_id,
        # 用当前世界的版本与回合取上界。`world_version` 与 `clock_tick` 是两套
        # 独立计数器，不能拿其中一个当另一个用。对已落盘的 id 集合来说这个界
        # 只会更宽，不会让未被引用的记忆混进来 —— 结果始终被 id 限死。
        current_world_version=world.world_version,
        current_clock_tick=world.clock_tick,
        query_text="plan evidence", scope=RetrievalScope.PUBLIC_EXPLANATION,
        allowed_memory_types=frozenset(MemoryType),
        limit=max(1, min(len(cited), 12)), char_budget=SUMMARY_MAX_LENGTH * 12,
    )
    rows = CognitionRepository(session).memories_by_id(request, cited)
    items: list[PlanEvidenceItem] = []
    for memory in rows:
        kind = SOURCE_KINDS[MEMORY_TYPE_KINDS[memory.memory_type]]
        items.append(PlanEvidenceItem(
            id=memory.id, type=memory.memory_type, label=SOURCE_LABELS[kind],
            summary=memory.safe_summary[:SUMMARY_MAX_LENGTH]))
    return items


def _to_plan_info(plan: AgentPlan, evidence: list[PlanEvidenceItem]) -> PlanInfo:
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
        evidence=evidence,
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
            current=None if current is None else _to_plan_info(
                current, _public_evidence(session, current)),
            # 历史计划只给形状，不逐条再查记忆 —— 那是 N 次额外查询，
            # 而「思考」Tab 的历史区只展示目标与状态。
            recent=[_to_plan_info(plan, []) for plan in recent],
        )
    except (SQLAlchemyError, ValidationError):
        # 计划行由本服务写入，形状异常属于服务端故障；对外仍是有界的 503。
        return JSONResponse(
            status_code=503,
            content=ErrorResponse(message="npc plan is unavailable").model_dump(),
        )

    return ApiResponse(data=data)
