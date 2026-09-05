from collections.abc import Iterable, Mapping

from backend.app.agents.action_registry import ActionRegistry
from backend.app.agents.contracts import (
    ActionProposal,
    ActionValidation,
    ResolvedProposal,
)
from backend.app.world.types import NpcSnapshot, WorldSnapshot


def resolve_proposals(
    world: WorldSnapshot,
    proposals: Iterable[ActionProposal],
    registry: ActionRegistry,
) -> tuple[ResolvedProposal, ...]:
    actors = {actor.id: actor for actor in world.npcs}
    indexed = tuple(enumerate(proposals))
    ordered = sorted(
        indexed,
        key=lambda item: _proposal_order(item[0], item[1], actors),
    )
    seen_known_actors: set[str] = set()
    resolutions: list[ResolvedProposal] = []

    for _, proposal in ordered:
        actor = actors.get(proposal.actor_id)
        if actor is None:
            validation = ActionValidation(
                False,
                "unknown_actor",
                "actor is absent from world snapshot",
            )
        elif proposal.actor_id in seen_known_actors:
            validation = ActionValidation(
                False,
                "duplicate_actor_proposal",
                "actor already has a proposal in this run",
            )
        else:
            seen_known_actors.add(proposal.actor_id)
            validation = registry.validate(proposal, actor, world)
        resolutions.append(ResolvedProposal(proposal, validation))

    return tuple(resolutions)


def _proposal_order(
    ordinal: int,
    proposal: ActionProposal,
    actors: Mapping[str, NpcSnapshot],
) -> tuple[int, int, str, int]:
    actor = actors.get(proposal.actor_id)
    if actor is None:
        return (1, 0, proposal.actor_id, ordinal)
    return (0, actor.sort_order, proposal.actor_id, ordinal)
