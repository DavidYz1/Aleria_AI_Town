from dataclasses import replace

import pytest

from backend.app.world.action_rules import ActionValidationError, execute_action
from backend.app.world.clock import advance_clock, get_time_phase
from backend.app.world.decision import decide_action
from backend.app.world.tick_engine import run_tick
from backend.app.world.types import (
    ActionPlan,
    LocationSnapshot,
    NpcSnapshot,
    WorldSnapshot,
)


LOCATIONS = (
    LocationSnapshot(id="tavern", name="星辉酒馆", sort_order=1),
    LocationSnapshot(id="park", name="中央公园", sort_order=2),
    LocationSnapshot(id="castle", name="晨曦城堡", sort_order=3),
    LocationSnapshot(id="forest", name="低语森林", sort_order=4),
)


def npc(
    npc_id: str,
    role: str,
    location_id: str,
    sort_order: int,
    *,
    energy: int = 80,
    mood: int = 70,
    social: int = 60,
) -> NpcSnapshot:
    return NpcSnapshot(
        id=npc_id,
        name=npc_id.title(),
        role=role,
        personality=("steady",),
        sort_order=sort_order,
        location_id=location_id,
        current_action="rest",
        energy=energy,
        mood=mood,
        social=social,
    )


def world(*npcs: NpcSnapshot, day: int = 1, time: str = "08:00", tick: int = 0):
    return WorldSnapshot(
        id="aleria-town",
        name="曦谷",
        day=day,
        time=time,
        tick=tick,
        locations=LOCATIONS,
        npcs=tuple(npcs),
    )


@pytest.mark.parametrize(
    ("day", "time", "want_day", "want_time"),
    [(1, "08:00", 1, "09:00"), (4, "23:00", 5, "00:00")],
)
def test_advance_clock_moves_exactly_one_hour_and_rolls_over_day(
    day, time, want_day, want_time
):
    assert advance_clock(day, time) == (want_day, want_time)


@pytest.mark.parametrize(
    ("time", "phase"),
    [
        ("05:59", "night"),
        ("06:00", "morning"),
        ("11:59", "morning"),
        ("12:00", "day"),
        ("17:59", "day"),
        ("18:00", "evening"),
        ("21:59", "evening"),
        ("22:00", "night"),
    ],
)
def test_get_time_phase_uses_approved_boundaries(time, phase):
    assert get_time_phase(time) == phase


def test_initial_morning_snapshot_produces_expected_actions():
    snapshot = world(
        npc("ryan", "Knight", "park", 1, energy=78, mood=77, social=67),
        npc("shir", "Assassin", "tavern", 2, energy=70, mood=64, social=32),
        npc("grey", "Guardian", "castle", 3, energy=86, mood=73, social=52),
        time="09:00",
    )

    actions = [decide_action(actor, snapshot) for actor in snapshot.npcs]

    assert [(a.actor_id, a.action_type, a.target_id) for a in actions] == [
        ("ryan", "work", None),
        ("shir", "move", "park"),
        ("grey", "work", None),
    ]


def test_night_and_low_energy_take_priority_over_role_routine():
    knight = npc("ryan", "Knight", "park", 1, energy=90)
    night_world = world(knight, time="22:00")
    tired_world = world(replace(knight, energy=30), time="12:00")

    assert decide_action(knight, night_world).action_type == "rest"
    assert decide_action(tired_world.npcs[0], tired_world).action_type == "rest"


def test_low_social_uses_sort_order_for_target_and_location():
    actor = npc("shir", "Assassin", "tavern", 2, social=40)
    ryan = npc("ryan", "Knight", "park", 1)
    grey = npc("grey", "Guardian", "park", 3)

    move = decide_action(actor, world(ryan, actor, grey, time="12:00"))
    together = decide_action(
        replace(actor, location_id="park"),
        world(ryan, replace(actor, location_id="park"), grey, time="12:00"),
    )

    assert (move.action_type, move.target_kind, move.target_id) == (
        "move",
        "location",
        "park",
    )
    assert (together.action_type, together.target_kind, together.target_id) == (
        "social",
        "npc",
        "ryan",
    )


def test_role_routines_change_with_phase_and_location():
    assassin = npc("shir", "Assassin", "park", 1)
    guardian = npc("grey", "Guardian", "tavern", 2)
    knight = npc("ryan", "Knight", "park", 3)
    snapshot = world(assassin, guardian, knight, time="18:00")

    assert decide_action(assassin, snapshot).target_id == "forest"
    assert decide_action(guardian, snapshot).target_id == "castle"
    assert decide_action(knight, snapshot).action_type == "social"


@pytest.mark.parametrize(
    ("npc_id", "role", "phase_time", "start", "action", "target", "reason"),
    [
        (
            "ryan", "Knight", "09:00", "tavern", "move", "park",
            "knight_training_travel",
        ),
        (
            "ryan", "Knight", "09:00", "park", "work", None,
            "knight_training",
        ),
        (
            "shir", "Assassin", "19:00", "tavern", "move", "forest",
            "assassin_scout_travel",
        ),
        (
            "shir", "Assassin", "19:00", "forest", "work", None,
            "assassin_scout",
        ),
        (
            "grey", "Guardian", "15:00", "park", "move", "castle",
            "guardian_patrol_travel",
        ),
        (
            "grey", "Guardian", "15:00", "castle", "work", None,
            "guardian_patrol",
        ),
    ],
)
def test_role_routines_use_character_duty_locations(
    npc_id,
    role,
    phase_time,
    start,
    action,
    target,
    reason,
):
    actor = npc(npc_id, role, start, 1, social=60)

    plan = decide_action(actor, world(actor, time=phase_time))

    assert (plan.action_type, plan.target_id, plan.reason) == (
        action,
        target,
        reason,
    )


def test_low_mood_moves_to_tavern_then_eats_when_already_there():
    actor = npc("shir", "Assassin", "park", 1, mood=35)
    move = decide_action(actor, world(actor, time="12:00"))
    at_tavern = replace(actor, location_id="tavern")
    eat = decide_action(at_tavern, world(at_tavern, time="12:00"))

    assert (move.action_type, move.target_id, move.reason) == (
        "move",
        "tavern",
        "low_mood_find_food",
    )
    assert (eat.action_type, eat.target_id, eat.reason) == (
        "eat",
        None,
        "low_mood_eat",
    )


def test_execute_action_validates_target_and_clamps_needs():
    actor = npc("ryan", "Knight", "park", 1, energy=98, mood=99, social=95)
    companion = npc("grey", "Guardian", "park", 2)
    snapshot = world(actor, companion, time="18:00")
    action = decide_action(actor, snapshot)

    updated = execute_action(actor, action, snapshot)

    assert (updated.energy, updated.mood, updated.social) == (96, 100, 100)
    with pytest.raises(ActionValidationError, match="same location"):
        execute_action(
            actor,
            replace(action, target_id="shir"),
            world(actor, npc("shir", "Assassin", "tavern", 3), time="18:00"),
        )


@pytest.mark.parametrize(
    ("actor", "action", "message"),
    [
        (
            npc("ryan", "Knight", "park", 1),
            ActionPlan("ryan", "move", "location", "missing", "test"),
            "valid location",
        ),
        (
            npc("ryan", "Knight", "tavern", 1),
            ActionPlan("ryan", "work", reason="test"),
            "actor duty location",
        ),
        (
            npc("shir", "Assassin", "park", 1),
            ActionPlan("shir", "eat", reason="test"),
            "tavern location",
        ),
    ],
)
def test_execute_action_rejects_invalid_location_requirements(actor, action, message):
    with pytest.raises(ActionValidationError, match=message):
        execute_action(actor, action, world(actor, time="12:00"))


@pytest.mark.parametrize(
    ("npc_id", "role", "location_id"),
    [
        ("ryan", "Knight", "park"),
        ("shir", "Assassin", "forest"),
        ("grey", "Guardian", "castle"),
    ],
)
def test_execute_work_accepts_each_actor_duty_location(
    npc_id,
    role,
    location_id,
):
    actor = npc(npc_id, role, location_id, 1)

    updated = execute_action(
        actor,
        ActionPlan(npc_id, "work", reason="test"),
        world(actor, time="12:00"),
    )

    assert (updated.location_id, updated.current_action) == (location_id, "work")


@pytest.mark.parametrize(
    ("npc_id", "role", "location_id"),
    [
        ("ryan", "Knight", "forest"),
        ("shir", "Assassin", "park"),
        ("grey", "Guardian", "tavern"),
    ],
)
def test_execute_work_rejects_the_wrong_actor_duty_location(
    npc_id,
    role,
    location_id,
):
    actor = npc(npc_id, role, location_id, 1)

    with pytest.raises(ActionValidationError, match="actor duty location"):
        execute_action(
            actor,
            ActionPlan(npc_id, "work", reason="test"),
            world(actor, time="12:00"),
        )


def test_execute_action_clamps_lower_need_boundary():
    actor = npc("ryan", "Knight", "park", 1, energy=1, mood=1, social=1)
    updated = execute_action(
        actor,
        ActionPlan("ryan", "work", reason="test"),
        world(actor, time="12:00"),
    )

    assert (updated.energy, updated.mood, updated.social) == (0, 0, 1)


def test_run_tick_is_repeatable_and_uses_one_shared_snapshot():
    initial = world(
        npc("ryan", "Knight", "park", 1, social=44),
        npc("shir", "Assassin", "tavern", 2, social=43),
        npc("grey", "Guardian", "castle", 3, social=60),
    )

    first = run_tick(initial)
    second = run_tick(initial)

    assert first == second
    assert [(a.actor_id, a.action_type, a.target_id) for a in first.actions] == [
        ("ryan", "work", None),
        ("shir", "move", "park"),
        ("grey", "work", None),
    ]
    # Shir cannot socialize with Ryan until the next tick: her move is not visible
    # inside the current shared decision snapshot.
    assert first.world.npcs[1].location_id == "park"
    assert len(first.events) == 3
    assert all(event.description for event in first.events)


def test_run_tick_outcomes_do_not_depend_on_input_npc_order():
    ordered = world(
        npc("ryan", "Knight", "park", 1, social=44),
        npc("shir", "Assassin", "tavern", 2, social=43),
        npc("grey", "Guardian", "park", 3, social=60),
    )
    reversed_input = replace(ordered, npcs=tuple(reversed(ordered.npcs)))

    first = run_tick(ordered)
    second = run_tick(reversed_input)

    assert {
        action.actor_id: (action.action_type, action.target_id)
        for action in first.actions
    } == {
        action.actor_id: (action.action_type, action.target_id)
        for action in second.actions
    }
    assert {
        actor.id: (actor.location_id, actor.energy, actor.mood, actor.social)
        for actor in first.world.npcs
    } == {
        actor.id: (actor.location_id, actor.energy, actor.mood, actor.social)
        for actor in second.world.npcs
    }
