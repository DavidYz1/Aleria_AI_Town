from backend.app.agents.contracts import ActionProposal, ProposalSource
from backend.app.world.clock import get_time_phase
from backend.app.world.role_routines import (
    WORK_LOCATION_BY_ROLE,
    WORK_REASON_BY_ROLE,
    WORK_TRAVEL_REASON_BY_ROLE,
)
from backend.app.world.types import NpcSnapshot, WorldSnapshot


def _proposal(
    actor: NpcSnapshot,
    action_type: str,
    target_kind: str | None = None,
    target_id: str | None = None,
    reason_code: str = "",
) -> ActionProposal:
    return ActionProposal(
        actor_id=actor.id,
        action_type=action_type,
        target_kind=target_kind,
        target_id=target_id,
        reason_code=reason_code,
        source=ProposalSource.DETERMINISTIC,
    )


def _move(actor: NpcSnapshot, location_id: str, reason_code: str) -> ActionProposal:
    return _proposal(actor, "move", "location", location_id, reason_code)


def _others(actor: NpcSnapshot, world: WorldSnapshot) -> list[NpcSnapshot]:
    return sorted(
        (npc for npc in world.npcs if npc.id != actor.id),
        key=lambda npc: (npc.sort_order, npc.id),
    )


def _social_target(actor: NpcSnapshot, world: WorldSnapshot) -> NpcSnapshot | None:
    return next(
        (npc for npc in _others(actor, world) if npc.location_id == actor.location_id),
        None,
    )


def decide_action(actor: NpcSnapshot, world: WorldSnapshot) -> ActionProposal:
    phase = get_time_phase(world.time)

    if phase == "night":
        return _proposal(actor, "rest", reason_code="night_rest")
    if actor.energy <= 30:
        return _proposal(actor, "rest", reason_code="low_energy")

    if actor.social <= 40:
        companion = _social_target(actor, world)
        if companion is not None:
            return _proposal(
                actor,
                "talk",
                "npc",
                companion.id,
                "low_social_with_companion",
            )
        candidates = _others(actor, world)
        if candidates:
            return _move(
                actor,
                candidates[0].location_id,
                "low_social_find_companion",
            )

    if actor.mood <= 35:
        if actor.location_id == "tavern":
            return _proposal(actor, "eat", reason_code="low_mood_eat")
        return _move(actor, "tavern", "low_mood_find_food")

    if actor.role == "Knight":
        if phase in ("morning", "day"):
            duty_location = WORK_LOCATION_BY_ROLE[actor.role]
            if actor.location_id != duty_location:
                return _move(
                    actor,
                    duty_location,
                    WORK_TRAVEL_REASON_BY_ROLE[actor.role],
                )
            return _proposal(
                actor,
                "work",
                reason_code=WORK_REASON_BY_ROLE[actor.role],
            )
        companion = _social_target(actor, world)
        if companion is not None:
            return _proposal(
                actor,
                "talk",
                "npc",
                companion.id,
                "knight_evening_social",
            )
        return _proposal(actor, "rest", reason_code="knight_evening_rest")

    if actor.role == "Assassin":
        if phase in ("morning", "day"):
            if actor.location_id != "tavern":
                return _move(actor, "tavern", "assassin_meal_travel")
            return _proposal(actor, "eat", reason_code="assassin_meal")

        duty_location = WORK_LOCATION_BY_ROLE[actor.role]
        if actor.location_id != duty_location:
            return _move(
                actor,
                duty_location,
                WORK_TRAVEL_REASON_BY_ROLE[actor.role],
            )
        return _proposal(
            actor,
            "work",
            reason_code=WORK_REASON_BY_ROLE[actor.role],
        )

    if actor.role == "Guardian":
        duty_location = WORK_LOCATION_BY_ROLE[actor.role]
        if actor.location_id != duty_location:
            return _move(
                actor,
                duty_location,
                WORK_TRAVEL_REASON_BY_ROLE[actor.role],
            )
        return _proposal(
            actor,
            "work",
            reason_code=WORK_REASON_BY_ROLE[actor.role],
        )

    return _proposal(actor, "rest", reason_code="unknown_role_rest")
