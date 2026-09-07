from dataclasses import dataclass, replace
from datetime import UTC, datetime
import json
import logging
import re
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.agents.contracts import AgentRuntimeResult, ProposalSource, to_json_compatible
from backend.app.agents.action_registry import ActionRegistry, clamp_need
from backend.app.agents.orchestrator import run_deterministic_advance
from backend.app.world.action_rules import DEFAULT_ACTION_REGISTRY
from backend.app.world.clock import advance_clock

from backend.app.database.action_compat import (
    to_public_action_type,
)
from backend.app.database.models import (
    Event,
    AgentRun,
    ActionProposalRecord,
    AgentTraceEntry,
    Location,
    NpcProfile,
    NpcState,
    WorldAction,
    WorldState,
)
from backend.app.database.world_repository import (
    CANONICAL_WORLD_ID,
    WorldUnavailableError,
)
from backend.app.database.world_version import (
    WorldVersionConflictError,
    bump_world_version,
)
from backend.app.world.types import (
    LocationSnapshot,
    NpcSnapshot,
    TickResult,
    WorldSnapshot,
)


logger = logging.getLogger(__name__)
REQUIRED_LOCATION_IDS = {"tavern", "park"}
REQUIRED_NPC_IDS = {"ryan", "shir", "grey"}
TARGET_KINDS = {"location", "npc"}


class WorldTickConflictError(RuntimeError):
    pass


class WorldTickPersistenceError(RuntimeError):
    pass


@dataclass(frozen=True)
class PersistedTick:
    result: TickResult
    actions: tuple[WorldAction, ...]
    events: tuple[Event, ...]


@dataclass(frozen=True)
class PersistedAgentRun:
    run: AgentRun
    result: AgentRuntimeResult
    actions: tuple[WorldAction, ...]
    events: tuple[Event, ...]


class WorldTickRepository:
    def __init__(self, session: Session, registry: ActionRegistry = DEFAULT_ACTION_REGISTRY) -> None:
        self._session = session
        self._registry = registry

    def persist_run(
        self, run_id: str, expected_world_version: int, result: AgentRuntimeResult,
        *, correlation_id: str | None = None,
    ) -> PersistedAgentRun:
        try:
            run_id = str(UUID(str(run_id)))
            correlation_id = str(UUID(str(correlation_id))) if correlation_id else str(uuid4())
            # Reads and complete validation precede any durable insert or CAS.
            self._session.expire_all()
            base = self.get_snapshot()
            if base.world_version != expected_world_version:
                raise WorldTickConflictError("world version conflict; refresh and retry")
            self._validate_result(base, result)
            now = datetime.now(UTC)
            run = AgentRun(
                id=run_id, world_id=base.id, mode="deterministic",
                trigger_type="world_advance", status="completed",
                base_world_version=base.world_version,
                resulting_world_version=result.world.world_version,
                base_clock_tick=base.clock_tick, resulting_clock_tick=result.world.clock_tick,
                correlation_id=correlation_id, created_at=now, started_at=now, completed_at=now,
            )
            proposals = tuple(ActionProposalRecord(
                run_id=run_id, ordinal=ordinal, actor_id=p.actor_id, action_type=p.action_type,
                target_kind=p.target_kind, target_id=p.target_id, reason_code=p.reason_code,
                source=p.source.value, payload_json=to_json_compatible(p.payload),
                status="accepted" if r.validation.accepted else "rejected",
                rejection_code=None if r.validation.accepted else r.validation.code,
                rejection_message=None if r.validation.accepted else "Proposal rejected",
            ) for ordinal, (p, r) in enumerate(zip(result.proposals, result.resolutions, strict=True)))
            traces = tuple(AgentTraceEntry(
                run_id=run_id, sequence=t.sequence, stage=t.stage, actor_id=t.actor_id,
                summary=self._trace_summary(t.stage), data_json=to_json_compatible(t.data), visibility=t.visibility, created_at=now,
            ) for t in result.traces)
            bump_world_version(self._session, base.id, expected_world_version)
            world = self._session.get(WorldState, base.id)
            world.day, world.time = result.world.day, result.world.time
            world.clock_tick = result.world.clock_tick
            world.event_sequence = result.world.event_sequence
            for npc in result.world.npcs:
                state = self._session.get(NpcState, npc.id)
                state.location_id, state.current_action = npc.location_id, npc.current_action
                state.energy, state.mood, state.social = npc.energy, npc.mood, npc.social
            self._session.add(run)
            self._session.flush()
            self._session.add_all(proposals)
            self._session.flush()
            accepted = tuple(p for p in proposals if p.status == "accepted")
            actions = tuple(WorldAction(
                world_id=base.id, run_id=run_id, proposal_id=p.id,
                clock_tick=world.clock_tick, world_version=world.world_version,
                actor_id=p.actor_id, action_type=p.action_type, target_kind=p.target_kind,
                target_id=p.target_id, reason_code=p.reason_code, status="executed",
                world_time=world.time, created_at=now,
            ) for p in accepted)
            self._session.add_all(actions)
            self._session.flush()
            events = tuple(Event(
                world_id=base.id, run_id=run_id, clock_tick=world.clock_tick,
                world_version=world.world_version, event_sequence=base.event_sequence + index,
                event_type=draft.event_type, actor_id=draft.actor_id, action_id=action.id,
                description=self._event_description(draft.actor_id, draft.event_type, draft.payload, base), world_time=world.time,
                payload_json=to_json_compatible(draft.payload), visibility=draft.visibility,
                secrecy=draft.visibility, causation_id=draft.causation_id,
                correlation_id=correlation_id, created_at=now,
            ) for index, (action, draft) in enumerate(zip(actions, result.events, strict=True), 1))
            self._session.add_all(events)
            self._session.add_all(traces)
            self._session.commit()
            return PersistedAgentRun(run=run, result=result, actions=actions, events=events)
        except (WorldTickConflictError, WorldVersionConflictError):
            self._session.rollback()
            raise WorldTickConflictError("world version conflict; refresh and retry") from None
        except (ValueError, TypeError, AttributeError, KeyError, WorldUnavailableError, WorldTickPersistenceError):
            self._session.rollback()
            raise WorldTickPersistenceError("invalid runtime result") from None
        except SQLAlchemyError:
            self._session.rollback()
            logger.warning("Failed to persist agent run")
            raise WorldTickPersistenceError("world tick persistence failed") from None

    def _validate_result(self, base: WorldSnapshot, result: AgentRuntimeResult) -> None:
        def require(condition: bool) -> None:
            if not condition:
                raise WorldTickPersistenceError("invalid runtime result")

        require(isinstance(result, AgentRuntimeResult))
        world = result.world
        require(all(type(value) is int for value in (
            world.world_version, world.clock_tick, world.event_sequence, world.day
        )))
        require(world.id == base.id and world.name == base.name)
        require(world.locations == base.locations)
        require(world.world_version == base.world_version + 1)
        require(world.clock_tick == base.clock_tick + 1)
        require((world.day, world.time) == advance_clock(base.day, base.time))
        require(world.event_sequence == base.event_sequence + len(result.events))
        require(len(result.resolutions) == len(result.proposals))
        decision_world = self._decision_snapshot(base)
        require(tuple(n.id for n in world.npcs) == tuple(n.id for n in decision_world.npcs))
        locations = {location.id for location in base.locations}
        actors = {npc.id: npc for npc in decision_world.npcs}
        for before, npc in zip(decision_world.npcs, world.npcs, strict=True):
            require((npc.name, npc.role, npc.personality, npc.sort_order) == (
                before.name, before.role, before.personality, before.sort_order
            ))
            require(npc.location_id in locations)
            # Rejected actions may leave the actor's preexisting action intact.
            require(npc.current_action == before.current_action or npc.current_action in self._registry.action_types)
            require(all(type(v) is int and 0 <= v <= 100 for v in (npc.energy, npc.mood, npc.social)))
        for ordinal, proposal in enumerate(result.proposals):
            require(isinstance(proposal.source, ProposalSource))
            require(proposal.payload == {})

        accepted = []
        seen_actors: set[str] = set()
        updated_actors = dict(actors)
        validations = []
        execution_facts = {}
        event_facts = {}
        for ordinal, (p, r) in enumerate(zip(result.proposals, result.resolutions, strict=True)):
            require(p == r.proposal and type(r.validation.accepted) is bool)
            require(self._is_identifier(p.actor_id))
            require(self._is_identifier(p.action_type))
            require(p.target_kind is None or p.target_kind in TARGET_KINDS)
            require((p.target_kind is None) == (p.target_id is None))
            require(p.target_id is None or self._is_identifier(p.target_id))
            require(self._is_reason_code(p.reason_code))
            require(isinstance(r.validation.code, str) and isinstance(r.validation.message, str))
            actor = actors.get(p.actor_id)
            if actor is None:
                expected_accepted = False
                expected_code = "unknown_actor"
            elif p.actor_id in seen_actors:
                expected_accepted = False
                expected_code = "duplicate_actor_proposal"
            else:
                seen_actors.add(p.actor_id)
                expected_validation = self._registry.validate(p, actor, decision_world)
                expected_accepted = expected_validation.accepted
                expected_code = expected_validation.code
            require(r.validation.accepted is expected_accepted)
            require(r.validation.code == expected_code)
            validations.append((ordinal, r.validation.accepted, r.validation.code))
            if expected_accepted:
                updated = self._registry.execute(p, actor, decision_world)
                updated_actors[p.actor_id] = updated
                accepted.append((ordinal, p))
                execution_facts[ordinal] = {
                    "proposal_ordinal": ordinal,
                    "action_type": p.action_type,
                    "before": self._actor_facts(actor),
                    "after": self._actor_facts(updated),
                }
                event_facts[ordinal] = {
                    "proposal_ordinal": ordinal,
                    "event_type": self._registry.event_metadata(p.action_type).event_type,
                }
        require(len({p.actor_id for _, p in accepted}) == len(accepted))
        require(len(result.events) == len(accepted))
        expected_world = replace(
            decision_world,
            world_version=base.world_version + 1,
            event_sequence=base.event_sequence + len(accepted),
            npcs=tuple(updated_actors[npc.id] for npc in decision_world.npcs),
        )
        require(world == expected_world)
        for (ordinal, p), e in zip(accepted, result.events, strict=True):
            require(e.actor_id == p.actor_id)
            require(e.payload == {
                "action_type": p.action_type,
                "target": self._target_facts(p),
                "reason_code": p.reason_code,
                "proposal_ordinal": ordinal,
            })
            require(e.event_type == self._registry.event_metadata(p.action_type).event_type)
            require(e.causation_id is None or self._is_uuid_reference(e.causation_id))
            require(e.visibility in {"public", "private"})
        require(bool(result.traces))
        require(tuple(t.sequence for t in result.traces) == tuple(range(1, len(result.traces) + 1)))
        require(result.traces[0].stage == "run_started" and result.traces[-1].stage == "run_completed")
        for t in result.traces:
            require(type(t.sequence) is int)
            require(t.visibility in {"public", "private"})
            if t.stage == "run_started":
                require(t.actor_id is None and t.data == {
                    "world_id": base.id,
                    "world_version": base.world_version,
                    "clock_tick": base.clock_tick,
                })
            elif t.stage == "proposal":
                ordinal = self._trace_ordinal(t.data, len(result.proposals))
                proposal = result.proposals[ordinal]
                require(t.actor_id == proposal.actor_id and t.data == {
                    "action_type": proposal.action_type,
                    "target": self._target_facts(proposal),
                    "reason_code": proposal.reason_code,
                    "proposal_ordinal": ordinal,
                    "source": proposal.source.value,
                })
            elif t.stage == "validation":
                ordinal = self._trace_ordinal(t.data, len(result.proposals))
                _, accepted_value, code = validations[ordinal]
                require(t.actor_id == result.proposals[ordinal].actor_id and t.data == {
                    "proposal_ordinal": ordinal,
                    "accepted": accepted_value,
                    "code": code,
                })
            elif t.stage == "execution":
                ordinal = self._trace_ordinal(t.data, len(result.proposals))
                require(ordinal in execution_facts and t.actor_id == result.proposals[ordinal].actor_id)
                require(t.data == execution_facts[ordinal])
            elif t.stage == "event":
                ordinal = self._trace_ordinal(t.data, len(result.proposals))
                require(ordinal in event_facts and t.actor_id == result.proposals[ordinal].actor_id)
                require(t.data == event_facts[ordinal])
            elif t.stage == "run_completed":
                require(t.actor_id is None and t.data == {
                    "world_id": world.id,
                    "world_version": world.world_version,
                    "clock_tick": world.clock_tick,
                    "event_sequence": world.event_sequence,
                    "accepted_count": len(accepted),
                    "rejected_count": len(result.resolutions) - len(accepted),
                })
            else:
                require(False)

    @staticmethod
    def _decision_snapshot(base: WorldSnapshot) -> WorldSnapshot:
        day, time = advance_clock(base.day, base.time)
        return replace(
            base,
            day=day,
            time=time,
            clock_tick=base.clock_tick + 1,
            npcs=tuple(
                replace(
                    npc,
                    energy=clamp_need(npc.energy - 2),
                    mood=clamp_need(npc.mood - 1),
                    social=clamp_need(npc.social - 3),
                )
                for npc in sorted(base.npcs, key=lambda npc: (npc.sort_order, npc.id))
            ),
        )

    @staticmethod
    def _is_identifier(value: object) -> bool:
        return isinstance(value, str) and bool(re.fullmatch(r"[a-z][a-z0-9-]{0,63}", value))

    @staticmethod
    def _is_reason_code(value: object) -> bool:
        return isinstance(value, str) and bool(re.fullmatch(r"[a-z][a-z0-9_]{0,63}", value))

    @staticmethod
    def _is_uuid_reference(value: object) -> bool:
        if not isinstance(value, str):
            return False
        try:
            return str(UUID(value)) == value
        except ValueError:
            return False

    @staticmethod
    def _target_facts(proposal) -> dict[str, str] | None:
        if proposal.target_kind is None:
            return None
        return {"kind": proposal.target_kind, "id": proposal.target_id}

    @staticmethod
    def _actor_facts(actor) -> dict[str, object]:
        return {
            "location_id": actor.location_id,
            "current_action": actor.current_action,
            "energy": actor.energy,
            "mood": actor.mood,
            "social": actor.social,
        }

    @staticmethod
    def _trace_ordinal(data, proposal_count: int) -> int:
        ordinal = data.get("proposal_ordinal")
        if type(ordinal) is not int or not 0 <= ordinal < proposal_count:
            raise WorldTickPersistenceError("invalid runtime result")
        return ordinal

    @staticmethod
    def _trace_summary(stage: str) -> str:
        return {
            "run_started": "Deterministic world advance started",
            "proposal": "Action proposed",
            "validation": "Proposal validated",
            "execution": "Action executed",
            "event": "Domain event recorded",
            "run_completed": "Deterministic world advance completed",
        }[stage]

    def _event_description(self, actor_id: str | None, event_type: str, payload, base: WorldSnapshot) -> str:
        actor = next(npc for npc in base.npcs if npc.id == actor_id)
        action_type = payload["action_type"]
        label = self._registry.event_metadata(action_type).public_label
        target = payload["target"]
        suffix = f" {target['id']}" if target is not None else ""
        return f"{actor.name} {label}{suffix}"

    def get_snapshot(self) -> WorldSnapshot:
        try:
            world = self._session.get(WorldState, CANONICAL_WORLD_ID)
            if world is None:
                raise WorldUnavailableError("world state is unavailable")
            locations = tuple(
                LocationSnapshot(
                    id=location.id,
                    name=location.name,
                    sort_order=location.sort_order,
                    description=location.description,
                )
                for location in self._session.scalars(
                    select(Location).order_by(Location.sort_order, Location.id)
                )
            )
            profiles = list(
                self._session.scalars(
                    select(NpcProfile).order_by(
                        NpcProfile.sort_order,
                        NpcProfile.id,
                    )
                )
            )
            states_by_npc = {
                state.npc_id: state
                for state in self._session.scalars(select(NpcState))
            }
            if (
                not REQUIRED_LOCATION_IDS.issubset(
                    {location.id for location in locations}
                )
                or not REQUIRED_NPC_IDS.issubset(
                    {profile.id for profile in profiles}
                )
                or any(profile.id not in states_by_npc for profile in profiles)
            ):
                raise WorldUnavailableError("world state is unavailable")

            npcs = tuple(
                NpcSnapshot(
                    id=profile.id,
                    name=profile.name,
                    role=profile.role,
                    personality=tuple(profile.personality_json),
                    sort_order=profile.sort_order,
                    location_id=states_by_npc[profile.id].location_id,
                    current_action=to_public_action_type(
                        states_by_npc[profile.id].current_action
                    ),
                    energy=states_by_npc[profile.id].energy,
                    mood=states_by_npc[profile.id].mood,
                    social=states_by_npc[profile.id].social,
                )
                for profile in profiles
            )
            return WorldSnapshot(
                id=world.id,
                name=world.name,
                day=world.day,
                time=world.time,
                clock_tick=world.clock_tick,
                world_version=world.world_version,
                event_sequence=world.event_sequence,
                locations=locations,
                npcs=npcs,
            )
        except WorldUnavailableError:
            raise
        except SQLAlchemyError as exc:
            logger.exception("Failed to load world tick snapshot", exc_info=exc)
            raise WorldUnavailableError("world state is unavailable") from None

    def persist_tick(self, expected_world_version: int, result: TickResult) -> PersistedTick:
        # Compatibility for existing in-process callers of the old pure facade.
        runtime = run_deterministic_advance(self.get_snapshot())
        if (result.world != runtime.world
            or result.actions != tuple(r.proposal for r in runtime.resolutions if r.validation.accepted)
            or tuple((e.actor_id,e.event_type,e.description) for e in result.events)
            != tuple((e.actor_id,e.event_type,e.description) for e in runtime.events)):
            self._session.rollback()
            raise WorldTickPersistenceError("invalid tick result")
        persisted = self.persist_run(str(uuid4()), expected_world_version, runtime)
        return PersistedTick(result=result, actions=persisted.actions, events=persisted.events)
