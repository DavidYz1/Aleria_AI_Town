from dataclasses import replace

from backend.app.world.action_rules import clamp_need, execute_action
from backend.app.world.clock import advance_clock
from backend.app.world.decision import decide_action
from backend.app.world.types import EventPlan, NpcSnapshot, TickResult, WorldSnapshot


def _apply_passive_drift(npc: NpcSnapshot) -> NpcSnapshot:
    return replace(
        npc,
        energy=clamp_need(npc.energy - 2),
        mood=clamp_need(npc.mood - 1),
        social=clamp_need(npc.social - 3),
    )


def _describe(actor: NpcSnapshot, action_type: str, target_id: str | None) -> str:
    labels = {
        "move": "前往",
        "rest": "休息",
        "work": "工作",
        "eat": "用餐",
        "social": "交谈",
    }
    suffix = f" {target_id}" if target_id else ""
    return f"{actor.name} {labels[action_type]}{suffix}"


def run_tick(world: WorldSnapshot) -> TickResult:
    day, time = advance_clock(world.day, world.time)
    drifted = tuple(_apply_passive_drift(npc) for npc in world.npcs)
    decision_world = replace(
        world,
        day=day,
        time=time,
        tick=world.tick + 1,
        npcs=drifted,
    )
    actions = tuple(decide_action(npc, decision_world) for npc in drifted)
    updated_npcs = tuple(
        execute_action(npc, action, decision_world)
        for npc, action in zip(drifted, actions, strict=True)
    )
    events = tuple(
        EventPlan(
            actor_id=actor.id,
            event_type="npc_action",
            description=_describe(actor, action.action_type, action.target_id),
        )
        for actor, action in zip(drifted, actions, strict=True)
    )
    return TickResult(
        world=replace(decision_world, npcs=updated_npcs),
        actions=actions,
        events=events,
    )
