from dataclasses import replace

from backend.app.world.role_routines import WORK_LOCATION_BY_ROLE
from backend.app.world.types import ActionPlan, NpcSnapshot, WorldSnapshot


class ActionValidationError(ValueError):
    pass


def clamp_need(value: int) -> int:
    return max(0, min(100, value))


def _validate_action(
    actor: NpcSnapshot, action: ActionPlan, world: WorldSnapshot
) -> None:
    if action.actor_id != actor.id:
        raise ActionValidationError("action actor does not match state actor")

    if action.action_type == "move":
        location_ids = {location.id for location in world.locations}
        if action.target_kind != "location" or action.target_id not in location_ids:
            raise ActionValidationError("move requires a valid location target")
        return

    if action.action_type == "social":
        target = next(
            (npc for npc in world.npcs if npc.id == action.target_id),
            None,
        )
        if (
            action.target_kind != "npc"
            or target is None
            or target.id == actor.id
            or target.location_id != actor.location_id
        ):
            raise ActionValidationError(
                "social target must be another NPC at the same location"
            )
        return

    if action.target_kind is not None or action.target_id is not None:
        raise ActionValidationError(f"{action.action_type} does not accept a target")
    if action.action_type == "work":
        duty_location = WORK_LOCATION_BY_ROLE.get(actor.role)
        if duty_location is None or actor.location_id != duty_location:
            raise ActionValidationError("work requires the actor duty location")
    if action.action_type == "eat" and actor.location_id != "tavern":
        raise ActionValidationError("eat requires the tavern location")
    if action.action_type not in {"rest", "work", "eat"}:
        raise ActionValidationError(f"unknown action: {action.action_type}")


def execute_action(
    actor: NpcSnapshot, action: ActionPlan, world: WorldSnapshot
) -> NpcSnapshot:
    _validate_action(actor, action, world)
    energy, mood, social = actor.energy, actor.mood, actor.social
    location_id = actor.location_id

    if action.action_type == "move":
        location_id = action.target_id or actor.location_id
        energy -= 5
    elif action.action_type == "rest":
        energy += 15
        mood += 2
    elif action.action_type == "work":
        energy -= 8
        mood -= 2
    elif action.action_type == "eat":
        energy += 5
        mood += 8
    elif action.action_type == "social":
        energy -= 2
        mood += 5
        social += 15

    return replace(
        actor,
        location_id=location_id,
        current_action=action.action_type,
        energy=clamp_need(energy),
        mood=clamp_need(mood),
        social=clamp_need(social),
    )
