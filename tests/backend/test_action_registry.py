from dataclasses import FrozenInstanceError

import pytest

from backend.app.agents.action_registry import build_default_action_registry
from backend.app.agents.contracts import (
    ActionProposal,
    DomainEventDraft,
    ProposalSource,
    RuntimeMode,
    TraceDraft,
    to_json_compatible,
)
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


def world(*npcs: NpcSnapshot) -> WorldSnapshot:
    return WorldSnapshot(
        id="aleria-town",
        name="曦谷",
        day=1,
        time="12:00",
        clock_tick=0,
        world_version=0,
        event_sequence=0,
        locations=LOCATIONS,
        npcs=tuple(npcs),
    )


@pytest.fixture
def registry():
    return build_default_action_registry()


def test_default_registry_action_types(registry):
    assert registry.action_types == (
        "eat",
        "move",
        "rest",
        "talk",
        "wait",
        "work",
    )


def test_unknown_action_is_rejected(registry):
    grey = npc("grey", "Guardian", "castle", 1)

    decision = registry.validate(
        ActionProposal(actor_id="grey", action_type="teleport"),
        grey,
        world(grey),
    )

    assert (decision.accepted, decision.code) == (False, "unknown_action")


def test_actor_mismatch_is_rejected(registry):
    grey = npc("grey", "Guardian", "castle", 1)

    decision = registry.validate(
        ActionProposal(actor_id="shir", action_type="rest"),
        grey,
        world(grey),
    )

    assert (decision.accepted, decision.code) == (False, "actor_mismatch")


@pytest.mark.parametrize(
    ("proposal", "code"),
    [
        (ActionProposal("ryan", "move", target_id="park"), "invalid_target"),
        (
            ActionProposal("ryan", "move", "location", None),
            "invalid_target",
        ),
        (
            ActionProposal("ryan", "rest", "location", "park"),
            "invalid_target",
        ),
    ],
)
def test_registry_rejects_wrong_target_shape(registry, proposal, code):
    ryan = npc("ryan", "Knight", "park", 1)

    decision = registry.validate(proposal, ryan, world(ryan))

    assert (decision.accepted, decision.code) == (False, code)


def test_move_requires_known_location_and_applies_move_effect(registry):
    ryan = npc("ryan", "Knight", "park", 1, energy=4)
    snapshot = world(ryan)
    missing = ActionProposal("ryan", "move", "location", "missing")
    proposal = ActionProposal("ryan", "move", "location", "castle")

    rejected = registry.validate(missing, ryan, snapshot)
    updated = registry.execute(proposal, ryan, snapshot)

    assert (rejected.accepted, rejected.code) == (False, "unknown_location")
    assert (updated.location_id, updated.current_action, updated.energy) == (
        "castle",
        "move",
        0,
    )


@pytest.mark.parametrize(
    ("role", "location_id"),
    [("Knight", "park"), ("Assassin", "forest"), ("Guardian", "castle")],
)
def test_work_requires_each_roles_duty_location(registry, role, location_id):
    actor = npc("actor", role, location_id, 1)
    proposal = ActionProposal("actor", "work")

    accepted = registry.validate(proposal, actor, world(actor))
    wrong_place = npc("actor", role, "tavern", 1)
    rejected = registry.validate(proposal, wrong_place, world(wrong_place))

    assert (accepted.accepted, accepted.code) == (True, "accepted")
    assert (rejected.accepted, rejected.code) == (
        False,
        "wrong_duty_location",
    )


def test_eat_requires_tavern_location(registry):
    at_tavern = npc("shir", "Assassin", "tavern", 1)
    at_park = npc("shir", "Assassin", "park", 1)
    proposal = ActionProposal("shir", "eat")

    accepted = registry.validate(proposal, at_tavern, world(at_tavern))
    rejected = registry.validate(proposal, at_park, world(at_park))

    assert accepted.accepted is True
    assert (rejected.accepted, rejected.code) == (False, "not_at_tavern")


def test_talk_requires_another_colocated_npc(registry):
    ryan = npc("ryan", "Knight", "park", 1)
    grey = npc("grey", "Guardian", "park", 2)
    shir = npc("shir", "Assassin", "tavern", 3)
    snapshot = world(ryan, grey, shir)

    accepted = registry.validate(
        ActionProposal("ryan", "talk", "npc", "grey"),
        ryan,
        snapshot,
    )
    self_target = registry.validate(
        ActionProposal("ryan", "talk", "npc", "ryan"),
        ryan,
        snapshot,
    )
    elsewhere = registry.validate(
        ActionProposal("ryan", "talk", "npc", "shir"),
        ryan,
        snapshot,
    )

    assert accepted.accepted is True
    assert (self_target.accepted, self_target.code) == (
        False,
        "talk_target_unavailable",
    )
    assert (elsewhere.accepted, elsewhere.code) == (
        False,
        "talk_target_unavailable",
    )


def test_wait_is_a_true_no_op(registry):
    actor = npc("grey", "Guardian", "castle", 1)
    snapshot = world(actor)

    updated = registry.execute(ActionProposal("grey", "wait"), actor, snapshot)

    assert updated is actor
    assert snapshot == world(actor)


def test_action_effects_clamp_needs_without_mutating_inputs(registry):
    actor = npc(
        "ryan",
        "Knight",
        "park",
        1,
        energy=1,
        mood=99,
        social=95,
    )
    companion = npc("grey", "Guardian", "park", 2)
    snapshot = world(actor, companion)
    proposal = ActionProposal("ryan", "talk", "npc", "grey")

    updated = registry.execute(proposal, actor, snapshot)

    assert (updated.energy, updated.mood, updated.social) == (0, 100, 100)
    assert snapshot.npcs[0] is actor
    assert (actor.energy, actor.mood, actor.social) == (1, 99, 95)


def test_contracts_deep_freeze_json_and_offer_explicit_serialization():
    source_payload = {"clues": [{"seen": True}], "score": 1.5}
    proposal = ActionProposal("grey", "wait", payload=source_payload)
    event = DomainEventDraft(
        event_type="npc_action",
        actor_id="grey",
        description="Grey waits",
        payload=source_payload,
        visibility="public",
    )
    trace = TraceDraft(
        sequence=1,
        stage="proposal",
        actor_id=None,
        summary="No action selected",
        data=source_payload,
        visibility="private",
    )
    source_payload["clues"][0]["seen"] = False

    assert to_json_compatible(proposal.payload) == {
        "clues": [{"seen": True}],
        "score": 1.5,
    }
    assert to_json_compatible(event.payload) == {
        "clues": [{"seen": True}],
        "score": 1.5,
    }
    assert to_json_compatible(trace.data) == {
        "clues": [{"seen": True}],
        "score": 1.5,
    }
    with pytest.raises(TypeError):
        proposal.payload["new"] = "value"
    with pytest.raises(FrozenInstanceError):
        proposal.action_type = "rest"


@pytest.mark.parametrize(
    "payload",
    [
        {"bad": object()},
        {"bad": {1: "non-string key"}},
        {"bad": float("nan")},
        {"bad": float("inf")},
        {"bad": float("-inf")},
    ],
)
def test_contracts_reject_values_that_are_not_json_safe(payload):
    with pytest.raises((TypeError, ValueError), match="JSON"):
        ActionProposal("grey", "wait", payload=payload)


def test_contracts_reject_cyclic_json_collections_explicitly():
    cycle: list[object] = []
    cycle.append(cycle)

    with pytest.raises(ValueError, match="JSON collection.*cyclic"):
        ActionProposal("grey", "wait", payload={"cycle": cycle})


def test_runtime_contract_enums_are_stable_strings():
    assert [mode.value for mode in RuntimeMode] == [
        "auto",
        "deterministic",
        "force_deliberation",
    ]
    assert [source.value for source in ProposalSource] == [
        "deterministic",
        "existing_plan",
        "llm",
        "fallback",
    ]
