from dataclasses import replace

from backend.app.agents.action_registry import (
    ActionDefinition,
    ActionRegistry,
    build_default_action_registry,
)
from backend.app.agents.conflict_resolver import resolve_proposals
from backend.app.agents.contracts import (
    ActionProposal,
    ActionValidation,
    to_json_compatible,
)
from backend.app.agents.orchestrator import run_deterministic_advance
from backend.app.world.types import LocationSnapshot, NpcSnapshot, WorldSnapshot


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


def world(
    *npcs: NpcSnapshot,
    day: int = 1,
    time: str = "08:00",
    clock_tick: int = 7,
    world_version: int = 11,
    event_sequence: int = 20,
) -> WorldSnapshot:
    return WorldSnapshot(
        id="aleria-town",
        name="曦谷",
        day=day,
        time=time,
        clock_tick=clock_tick,
        world_version=world_version,
        event_sequence=event_sequence,
        locations=LOCATIONS,
        npcs=tuple(npcs),
    )


def test_resolver_orders_known_actors_and_is_input_order_independent():
    grey = npc("grey", "Guardian", "castle", 2)
    ryan = npc("ryan", "Knight", "park", 1)
    snapshot = world(grey, ryan)
    grey_proposal = ActionProposal("grey", "work", reason_code="patrol")
    ryan_proposal = ActionProposal("ryan", "work", reason_code="training")
    registry = build_default_action_registry()

    forward = resolve_proposals(
        snapshot,
        (grey_proposal, ryan_proposal),
        registry,
    )
    reverse = resolve_proposals(
        snapshot,
        (ryan_proposal, grey_proposal),
        registry,
    )

    assert forward == reverse
    assert [item.proposal.actor_id for item in forward] == ["ryan", "grey"]
    assert all(item.validation.accepted for item in forward)


def test_resolver_puts_unknown_actors_last_and_rejects_them():
    grey = npc("grey", "Guardian", "castle", 1)
    snapshot = world(grey)

    resolutions = resolve_proposals(
        snapshot,
        (
            ActionProposal("missing", "rest"),
            ActionProposal("grey", "work"),
        ),
        build_default_action_registry(),
    )

    assert [item.proposal.actor_id for item in resolutions] == ["grey", "missing"]
    assert resolutions[1].validation.code == "unknown_actor"


def test_resolver_considers_only_the_first_duplicate_actor_proposal():
    ryan = npc("ryan", "Knight", "park", 1)
    first = ActionProposal("ryan", "teleport")
    second = ActionProposal("ryan", "work")

    resolutions = resolve_proposals(
        world(ryan),
        (first, second),
        build_default_action_registry(),
    )

    assert len(resolutions) == 2
    assert resolutions[0].proposal is first
    assert resolutions[0].validation.code == "unknown_action"
    assert resolutions[1].proposal is second
    assert resolutions[1].validation.code == "duplicate_actor_proposal"


def test_resolver_preserves_registry_rejection_and_never_mutates_world():
    ryan = npc("ryan", "Knight", "tavern", 1)
    snapshot = world(ryan)
    original = replace(snapshot)

    resolutions = resolve_proposals(
        snapshot,
        (ActionProposal("ryan", "work"),),
        build_default_action_registry(),
    )

    assert len(resolutions) == 1
    resolution = resolutions[0]
    assert (resolution.validation.code, resolution.validation.message) == (
        "wrong_duty_location",
        "work requires the actor duty location",
    )
    assert snapshot == original


def test_advance_is_stable_for_permuted_snapshots_and_updates_counters_once():
    ordered = world(
        npc("ryan", "Knight", "park", 1, social=44),
        npc("shir", "Assassin", "tavern", 2, social=43),
        npc("grey", "Guardian", "castle", 3, social=60),
    )
    permuted = replace(ordered, npcs=tuple(reversed(ordered.npcs)))

    first = run_deterministic_advance(ordered)
    second = run_deterministic_advance(permuted)

    assert first == second
    assert [proposal.actor_id for proposal in first.proposals] == [
        "ryan",
        "shir",
        "grey",
    ]
    assert (first.world.day, first.world.time) == (1, "09:00")
    assert first.world.clock_tick == 8
    assert first.world.world_version == 12
    assert first.world.event_sequence == 23


def test_all_decisions_share_the_post_drift_snapshot_and_rejections_keep_drift():
    initial = world(
        npc("ryan", "Knight", "park", 1, social=44),
        npc("shir", "Assassin", "tavern", 2, social=43),
    )

    result = run_deterministic_advance(initial)
    rejected = run_deterministic_advance(initial, registry=ActionRegistry(()))

    assert [
        (proposal.actor_id, proposal.action_type, proposal.target_id)
        for proposal in result.proposals
    ] == [
        ("ryan", "work", None),
        ("shir", "move", "park"),
    ]
    assert rejected.events == ()
    assert [resolution.validation.code for resolution in rejected.resolutions] == [
        "unknown_action",
        "unknown_action",
    ]
    assert [
        (actor.id, actor.energy, actor.mood, actor.social)
        for actor in rejected.world.npcs
    ] == [
        ("ryan", 78, 69, 41),
        ("shir", 78, 69, 40),
    ]
    assert rejected.world.event_sequence == initial.event_sequence
    assert [trace.stage for trace in rejected.traces] == [
        "run_started",
        "proposal",
        "proposal",
        "validation",
        "validation",
        "run_completed",
    ]
    assert to_json_compatible(result.events[1].payload)["target"] == {
        "kind": "location",
        "id": "park",
    }


def test_events_and_traces_are_factual_structured_and_gap_free():
    initial = world(npc("ryan", "Knight", "park", 1))

    result = run_deterministic_advance(initial)

    assert len(result.events) == 1
    event = result.events[0]
    assert (event.event_type, event.description, event.visibility) == (
        "npc_action",
        "Ryan 工作",
        "public",
    )
    assert to_json_compatible(event.payload) == {
        "action_type": "work",
        "target": None,
        "reason_code": "knight_training",
        "proposal_ordinal": 0,
    }
    assert result.traces[0].stage == "run_started"
    assert result.traces[-1].stage == "run_completed"
    assert [trace.sequence for trace in result.traces] == list(
        range(1, len(result.traces) + 1)
    )
    assert {trace.stage for trace in result.traces} == {
        "run_started",
        "proposal",
        "validation",
        "execution",
        "event",
        "run_completed",
    }
    assert all(
        "chain_of_thought" not in to_json_compatible(trace.data)
        for trace in result.traces
    )


def test_event_type_and_description_use_registry_metadata():
    def accept(proposal, actor, snapshot):
        return ActionValidation(True, "accepted", "action accepted")

    def leave_actor_unchanged(proposal, actor, snapshot):
        return actor

    registry = ActionRegistry(
        (
            ActionDefinition(
                "work",
                None,
                accept,
                leave_actor_unchanged,
                "custom_training_event",
                "训练",
            ),
        )
    )

    result = run_deterministic_advance(
        world(npc("ryan", "Knight", "park", 1)),
        registry=registry,
    )

    assert (result.events[0].event_type, result.events[0].description) == (
        "custom_training_event",
        "Ryan 训练",
    )
