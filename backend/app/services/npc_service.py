from backend.app.database.npc_repository import NpcRepository
from backend.app.schemas.npc import (
    NpcDetailData,
    NpcProfileDetail,
    NpcRecentAction,
    NpcStateDetail,
    NpcWorldContext,
)
from backend.app.schemas.world import NpcStatus
from backend.app.services.action_explanation import explain_action
from backend.app.world.clock import get_time_phase


class NpcService:
    def __init__(self, repository: NpcRepository) -> None:
        self._repository = repository

    def get_detail(self, npc_id: str) -> NpcDetailData:
        records = self._repository.get_detail_records(npc_id)
        recent_actions: list[NpcRecentAction] = []
        for action in records.actions:
            target_name = None
            if action.target_kind is not None and action.target_id is not None:
                target_name = records.target_names.get(
                    (action.target_kind, action.target_id),
                    action.target_id,
                )
            recent_actions.append(
                NpcRecentAction(
                    id=action.id,
                    tick=action.tick,
                    world_time=action.world_time,
                    action_type=action.action_type,
                    target_kind=action.target_kind,
                    target_id=action.target_id,
                    target_name=target_name,
                    reason_code=action.reason,
                    reason_text=explain_action(action.reason, target_name),
                )
            )

        return NpcDetailData(
            profile=NpcProfileDetail(
                id=records.profile.id,
                name=records.profile.name,
                role=records.profile.role,
                personality=list(records.profile.personality_json),
            ),
            state=NpcStateDetail(
                location_id=records.state.location_id,
                location_name=records.location.name,
                current_action=records.state.current_action,
                status=NpcStatus(
                    energy=records.state.energy,
                    mood=records.state.mood,
                    social=records.state.social,
                ),
            ),
            world_context=NpcWorldContext(
                day=records.world.day,
                time=records.world.time,
                tick=records.world.tick,
                time_phase=get_time_phase(records.world.time),
            ),
            recent_actions=recent_actions,
        )
