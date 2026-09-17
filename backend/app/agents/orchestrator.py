from collections.abc import Mapping
from dataclasses import replace

from backend.app.agents.action_registry import (
    ActionRegistry,
    clamp_need,
)
from backend.app.agents.conflict_resolver import resolve_proposals
from backend.app.agents.contracts import (
    ActionProposal,
    ActionValidation,
    AgentRuntimeResult,
    DomainEventDraft,
    JsonValue,
    ProposalSource,
    TraceDraft,
)
from backend.app.world.clock import advance_clock
from backend.app.world.decision import decide_action
from backend.app.world.action_rules import DEFAULT_ACTION_REGISTRY
from backend.app.world.types import NpcSnapshot, WorldSnapshot


def run_advance(
    world: WorldSnapshot,
    registry: ActionRegistry = DEFAULT_ACTION_REGISTRY,
    proposal_override: Mapping[str, ActionProposal] | None = None,
) -> AgentRuntimeResult:
    ordered_npcs = tuple(
        sorted(world.npcs, key=lambda npc: (npc.sort_order, npc.id))
    )
    drifted_npcs = tuple(_apply_passive_drift(npc) for npc in ordered_npcs)
    day, time = advance_clock(world.day, world.time)
    decision_world = replace(
        world,
        day=day,
        time=time,
        clock_tick=world.clock_tick + 1,
        npcs=drifted_npcs,
    )
    override = proposal_override or {}
    initial = tuple(
        override.get(actor.id) or decide_action(actor, decision_world)
        for actor in decision_world.npcs
    )
    screened = tuple(
        _with_fallback(proposal, actor, decision_world, registry)
        for proposal, actor in zip(initial, decision_world.npcs, strict=True)
    )
    proposals = tuple(proposal for proposal, _ in screened)
    rejections = tuple(item for _, item in screened if item is not None)
    resolutions = resolve_proposals(decision_world, proposals, registry)

    traces: list[TraceDraft] = []
    _append_trace(
        traces,
        "run_started",
        None,
        "Deterministic world advance started",
        {
            "world_id": world.id,
            "world_version": world.world_version,
            "clock_tick": world.clock_tick,
        },
    )
    for rejection in rejections:
        _append_trace(
            traces,
            "rule_rejection",
            str(rejection["npc_id"]),
            f"Proposal rejected: {rejection['failure_code']}",
            rejection,
        )
    for ordinal, proposal in enumerate(proposals):
        _append_trace(
            traces,
            "proposal",
            proposal.actor_id,
            f"{proposal.actor_id} proposed {proposal.action_type}",
            {**_proposal_data(proposal, ordinal), "source": proposal.source.value},
        )
    for ordinal, resolution in enumerate(resolutions):
        validation = resolution.validation
        _append_trace(
            traces,
            "validation",
            resolution.proposal.actor_id,
            f"Proposal validation: {validation.code}",
            {
                "proposal_ordinal": ordinal,
                "accepted": validation.accepted,
                "code": validation.code,
            },
        )

    actors = {actor.id: actor for actor in decision_world.npcs}
    updated_actors = dict(actors)
    events: list[DomainEventDraft] = []
    for ordinal, resolution in enumerate(resolutions):
        if not resolution.validation.accepted:
            continue
        proposal = resolution.proposal
        actor = actors[proposal.actor_id]
        updated = registry.execute(proposal, actor, decision_world)
        updated_actors[actor.id] = updated
        metadata = registry.event_metadata(proposal.action_type)
        event = DomainEventDraft(
            event_type=metadata.event_type,
            actor_id=actor.id,
            description=_describe(
                actor,
                metadata.public_label,
                proposal.target_id,
            ),
            payload=_proposal_data(proposal, ordinal),
            visibility="public",
        )
        events.append(event)
        _append_trace(
            traces,
            "execution",
            actor.id,
            f"Executed {proposal.action_type}",
            {
                "proposal_ordinal": ordinal,
                "action_type": proposal.action_type,
                "before": _actor_state(actor),
                "after": _actor_state(updated),
            },
        )
        _append_trace(
            traces,
            "event",
            actor.id,
            event.description,
            {
                "proposal_ordinal": ordinal,
                "event_type": event.event_type,
            },
        )

    final_world = replace(
        decision_world,
        world_version=world.world_version + 1,
        event_sequence=world.event_sequence + len(events),
        npcs=tuple(updated_actors[actor.id] for actor in decision_world.npcs),
    )
    _append_trace(
        traces,
        "run_completed",
        None,
        "Deterministic world advance completed",
        {
            "world_id": final_world.id,
            "world_version": final_world.world_version,
            "clock_tick": final_world.clock_tick,
            "event_sequence": final_world.event_sequence,
            "accepted_count": len(events),
            "rejected_count": len(resolutions) - len(events),
        },
    )
    return AgentRuntimeResult(
        world=final_world,
        proposals=proposals,
        resolutions=resolutions,
        events=tuple(events),
        traces=tuple(traces),
    )


def _with_fallback(
    proposal: ActionProposal,
    actor: NpcSnapshot,
    world: WorldSnapshot,
    registry: ActionRegistry,
) -> tuple[ActionProposal, Mapping[str, JsonValue] | None]:
    """外部提案被拒绝时替换为确定性兜底。spec §13 唯一不变量。

    第二个返回值是**被替换掉的那个提案**的留痕。以前这里只取 `.accepted`，于是
    拒绝码和原始动作一起消失：替换之后 proposal trace 记的是兜底动作，validation
    trace 的 code 甚至是 `accepted`（它验证的是替换后的提案）。结果就是评测能报出
    「3 次 rule_rejected」却答不出「哪 3 次、什么动作、被哪条规则拒」。

    仍然不在这里写 trace —— 本函数保持纯函数，由调用方统一组装。
    """
    if proposal.source is ProposalSource.DETERMINISTIC:
        return proposal, None
    try:
        validation = registry.validate(proposal, actor, world)
    except Exception:
        # 校验器本身抛异常：拒绝提案，但绝不臆造一个具体拒绝码。
        validation = ActionValidation(False, "validator_error", "validator raised")
    if validation.accepted:
        return proposal, None
    target: JsonValue = None
    if proposal.target_kind is not None and proposal.target_id is not None:
        target = {"kind": proposal.target_kind, "id": proposal.target_id}
    rejection: Mapping[str, JsonValue] = {
        "npc_id": actor.id,
        "failure_stage": "rule",
        "failure_code": validation.code,
        "attempted_action": proposal.action_type,
        "attempted_target": target,
        "attempted_source": proposal.source.value,
    }
    return replace(decide_action(actor, world), source=ProposalSource.FALLBACK), rejection


def _apply_passive_drift(npc: NpcSnapshot) -> NpcSnapshot:
    return replace(
        npc,
        energy=clamp_need(npc.energy - 2),
        mood=clamp_need(npc.mood - 1),
        social=clamp_need(npc.social - 3),
    )


def _proposal_data(
    proposal: ActionProposal,
    ordinal: int,
) -> dict[str, JsonValue]:
    target: JsonValue = None
    if proposal.target_kind is not None and proposal.target_id is not None:
        target = {"kind": proposal.target_kind, "id": proposal.target_id}
    return {
        "action_type": proposal.action_type,
        "target": target,
        "reason_code": proposal.reason_code,
        "proposal_ordinal": ordinal,
    }


def _actor_state(actor: NpcSnapshot) -> dict[str, JsonValue]:
    return {
        "location_id": actor.location_id,
        "current_action": actor.current_action,
        "energy": actor.energy,
        "mood": actor.mood,
        "social": actor.social,
    }


def _describe(
    actor: NpcSnapshot,
    public_label: str,
    target_id: str | None,
) -> str:
    suffix = f" {target_id}" if target_id else ""
    return f"{actor.name} {public_label}{suffix}"


def _append_trace(
    traces: list[TraceDraft],
    stage: str,
    actor_id: str | None,
    summary: str,
    data: dict[str, JsonValue],
) -> None:
    traces.append(
        TraceDraft(
            sequence=len(traces) + 1,
            stage=stage,
            actor_id=actor_id,
            summary=summary,
            data=data,
        )
    )


# 向后兼容：现有 11 处调用继续使用此名称
run_deterministic_advance = run_advance
