from backend.app.world.clock import get_time_phase
from backend.app.world.role_routines import (
    WORK_LOCATION_BY_ROLE,
    WORK_REASON_BY_ROLE,
    WORK_TRAVEL_REASON_BY_ROLE,
)
from backend.app.world.types import ActionPlan, NpcSnapshot, WorldSnapshot


def _move(actor: NpcSnapshot, location_id: str, reason: str) -> ActionPlan:
    return ActionPlan(actor.id, "move", "location", location_id, reason)


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


def decide_action(actor: NpcSnapshot, world: WorldSnapshot) -> ActionPlan:
    phase = get_time_phase(world.time)

    if phase == "night":
        return ActionPlan(actor.id, "rest", reason="night_rest")
    if actor.energy <= 30:
        return ActionPlan(actor.id, "rest", reason="low_energy")

    if actor.social <= 40:
        companion = _social_target(actor, world)
        if companion is not None:
            return ActionPlan(
                actor.id,
                "social",
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
            return ActionPlan(actor.id, "eat", reason="low_mood_eat")
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
            return ActionPlan(
                actor.id,
                "work",
                reason=WORK_REASON_BY_ROLE[actor.role],
            )
        companion = _social_target(actor, world)
        if companion is not None:
            return ActionPlan(
                actor.id,
                "social",
                "npc",
                companion.id,
                "knight_evening_social",
            )
        return ActionPlan(actor.id, "rest", reason="knight_evening_rest")

    if actor.role == "Assassin":
        if phase in ("morning", "day"):
            if actor.location_id != "tavern":
                return _move(actor, "tavern", "assassin_meal_travel")
            return ActionPlan(actor.id, "eat", reason="assassin_meal")

        duty_location = WORK_LOCATION_BY_ROLE[actor.role]
        if actor.location_id != duty_location:
            return _move(
                actor,
                duty_location,
                WORK_TRAVEL_REASON_BY_ROLE[actor.role],
            )
        return ActionPlan(
            actor.id,
            "work",
            reason=WORK_REASON_BY_ROLE[actor.role],
        )

    if actor.role == "Guardian":
        duty_location = WORK_LOCATION_BY_ROLE[actor.role]
        if actor.location_id != duty_location:
            return _move(
                actor,
                duty_location,
                WORK_TRAVEL_REASON_BY_ROLE[actor.role],
            )
        return ActionPlan(
            actor.id,
            "work",
            reason=WORK_REASON_BY_ROLE[actor.role],
        )

    return ActionPlan(actor.id, "rest", reason="unknown_role_rest")
