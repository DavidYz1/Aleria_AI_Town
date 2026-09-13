"""Owner-scoped core projection. The caller owns commit/rollback."""
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
import json
from uuid import NAMESPACE_URL, uuid5, uuid4

from sqlalchemy import case, func, select, or_, bindparam, cast, Float, String, tuple_, update
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import Session

from backend.app.agents.cognition_contracts import ObservationDraft, SourceKind
from backend.app.agents.contracts import to_json_compatible
from backend.app.agents.perception import PerceptionPolicyRegistry
from backend.app.database.models import (
    AgentCognitionState, Conversation, ConversationMessage, Event, Memory,
    NpcProfile, Observation, WorldState, Belief, BeliefEvidence, MemoryEvidence,
)


@dataclass(frozen=True)
class ProjectionResult:
    created_observations: int = 0
    created_memories: int = 0


@dataclass(frozen=True)
class ConversationTurn:
    conversation: Conversation
    messages: tuple[ConversationMessage, ...]


@dataclass(frozen=True)
class SourceBatch:
    events: tuple[Event, ...]
    turns: tuple[ConversationTurn, ...]
    npc_profiles: tuple[NpcProfile, ...]
    event_upper: int
    message_upper: int


class CognitionRepository:
    def __init__(self, session: Session):
        self.session = session
        self._batches: dict[tuple[str, str], SourceBatch] = {}

    def reflection_context(self, world_id, owner_npc_id):
        """Caller owns the short read transaction; never pass ORM rows to a provider."""
        from types import SimpleNamespace
        state = self.get_or_create_state(world_id, owner_npc_id)
        world = self.session.get(WorldState, world_id, populate_existing=True)
        latest = self.session.execute(select(Memory.created_at, Memory.id).where(
            Memory.world_id == world_id, Memory.owner_npc_id == owner_npc_id,
            Memory.memory_type != "reflection", Memory.created_world_version <= world.world_version,
            Memory.created_clock_tick <= world.clock_tick).order_by(Memory.created_at.desc(), Memory.id.desc()).limit(1)).first()
        beliefs = tuple(self.session.scalars(select(Belief).join(Memory, Memory.id == Belief.source_reflection_memory_id).where(
            Belief.world_id == world_id, Belief.owner_npc_id == owner_npc_id,
            Belief.lifecycle_state == "active", Belief.created_world_version <= world.world_version,
            Belief.created_clock_tick <= world.clock_tick, Memory.world_id == world_id,
            Memory.owner_npc_id == owner_npc_id, Memory.memory_type == "reflection",
            Memory.lifecycle_state.in_(("active", "disputed")),
            Memory.occurred_world_version <= world.world_version, Memory.created_world_version <= world.world_version,
            Memory.occurred_clock_tick <= world.clock_tick, Memory.created_clock_tick <= world.clock_tick
        ).order_by(Belief.created_at.desc(), Belief.id).limit(12)))
        from backend.app.llm.reflection_provider import CurrentBelief
        return SimpleNamespace(reflection_pending_critical=state.reflection_pending_critical,
            reflection_memory_count=state.reflection_memory_count,
            reflection_accumulated_importance=state.reflection_accumulated_importance,
            reflection_attempt_fingerprint=state.reflection_attempt_fingerprint,
            reflection_attempt_count=state.reflection_attempt_count,
            current_world_version=world.world_version, current_clock_tick=world.clock_tick,
            source_cursor=tuple(latest) if latest else None,
            current_beliefs=tuple(CurrentBelief(belief_id=b.id, statement=b.statement,
                confidence=b.confidence, lifecycle_state=b.lifecycle_state) for b in beliefs))

    @staticmethod
    def reflection_memory_id(world_id, owner_npc_id, fingerprint):
        return str(uuid5(NAMESPACE_URL, "aleria:reflection:" + json.dumps(
            [world_id, owner_npc_id, fingerprint], separators=(",", ":"))))

    def reflection_attempt_allowed(self, world_id, owner_npc_id, fingerprint):
        state = self.get_or_create_state(world_id, owner_npc_id)
        if (state.last_reflection_evidence_fingerprint == fingerprint or
                self.session.get(Memory, self.reflection_memory_id(world_id, owner_npc_id, fingerprint)) is not None):
            return False
        return state.reflection_attempt_fingerprint != fingerprint or state.reflection_attempt_count < 2

    def record_reflection_failure(self, world_id, owner_npc_id, fingerprint):
        state = self.get_or_create_state(world_id, owner_npc_id)
        # Reservation already consumed the slot. Late failures must not replace
        # a newer batch or turn a concurrently successful batch into failed.
        if state.reflection_attempt_fingerprint != fingerprint or state.reflection_attempt_status == "succeeded":
            return
        state.reflection_attempt_status = "failed"
        state.updated_at = datetime.now(UTC)
        self.session.flush()

    def reserve_reflection_attempt(self, world_id, owner_npc_id, fingerprint, source_cursor):
        """An atomic UPDATE locks the state row on both PostgreSQL and SQLite.

        The conservative failed status includes abandoned/in-flight attempts;
        a crash therefore consumes its slot without a new lifecycle value.
        """
        if source_cursor is None:
            return False
        state = AgentCognitionState
        newer_source = select(Memory.id).where(Memory.world_id == world_id,
            Memory.owner_npc_id == owner_npc_id, Memory.memory_type != "reflection",
            tuple_(Memory.created_at, Memory.id) > source_cursor).exists()
        result = self.session.execute(update(state).where(
            state.world_id == world_id, state.owner_npc_id == owner_npc_id,
            or_(state.reflection_attempt_fingerprint.is_(None), state.reflection_attempt_fingerprint != fingerprint,
                state.reflection_attempt_count < 2),
            or_(state.last_reflection_evidence_fingerprint.is_(None), state.last_reflection_evidence_fingerprint != fingerprint),
            or_(state.last_reflection_source_created_at.is_(None),
                tuple_(state.last_reflection_source_created_at, state.last_reflection_source_memory_id) < source_cursor),
            ~newer_source,
        ).values(reflection_attempt_fingerprint=fingerprint,
            reflection_attempt_count=case((state.reflection_attempt_fingerprint == fingerprint,
                state.reflection_attempt_count + 1), else_=1),
            reflection_attempt_status="failed", updated_at=datetime.now(UTC))
            .execution_options(synchronize_session=False))
        return result.rowcount == 1

    def reflection_candidate_rows(self, request, source_cursor):
        # Immutable source creation order, bounded by the captured source cursor.
        # Embedding availability, access telemetry and advancing world recency
        # cannot change the candidate set for the same committed source progress.
        return tuple(self.session.scalars(select(Memory).where(*self._memory_filters(request),
            tuple_(Memory.created_at, Memory.id) <= source_cursor)
            .order_by(Memory.created_at.desc(), Memory.id.desc()).limit(50)))

    def reflection_permission_floor(self, request):
        """Pin the disclosure floor before exposing any text to the provider."""
        from backend.app.agents.reflection import ReflectionValidationError
        from backend.app.agents.memory_retrieval import memory_text
        ids = {str(c.memory_id) for c in request.candidates}
        rows = tuple(self.session.scalars(select(Memory).where(Memory.id.in_(ids))))
        texts = {str(c.memory_id): c.content for c in request.candidates}
        if len(rows) != len(ids) or any(memory_text(row) != texts[row.id] for row in rows):
            raise ReflectionValidationError("reflection evidence is invalid")
        belief_ids = {str(b.belief_id) for b in request.current_beliefs}
        beliefs = tuple(self.session.scalars(select(Belief).where(Belief.id.in_(belief_ids))))
        expected = {str(b.belief_id): (b.statement, b.confidence, b.lifecycle_state) for b in request.current_beliefs}
        if len(beliefs) != len(belief_ids) or any(
            (b.statement, b.confidence, b.lifecycle_state) != expected[b.id] for b in beliefs):
            raise ReflectionValidationError("reflection evidence is invalid")
        sources = tuple(self.session.scalars(select(Memory).where(Memory.id.in_(
            {b.source_reflection_memory_id for b in beliefs}))))
        visible = rows + sources
        return (max((r.secrecy for r in visible), key=("public", "private", "secret").index),
            max((r.disclosure_scope for r in visible), key=("public", "player_dialogue", "internal_only").index))

    def persist_reflection(self, world_id, owner_npc_id, draft, *, candidate_ids,
                           current_belief_ids, fingerprint, source_cursor, permission_floor=("public", "public"),
                           reserved=False):
        """Recheck all authority under locks; caller atomically commits or rolls back."""
        from backend.app.agents.cognition_contracts import ReflectionDraft
        from backend.app.agents.reflection import ReflectionValidationError, evidence_fingerprint
        draft = ReflectionDraft.model_validate(draft)
        candidate_ids = frozenset(map(str, candidate_ids))
        evidence_ids = tuple(map(str, draft.evidence_memory_ids))
        belief = draft.belief
        belief_ids = set() if belief is None else set(map(str,
            (*belief.supporting_memory_ids, *belief.contradicting_memory_ids)))
        if (not candidate_ids or fingerprint != evidence_fingerprint(candidate_ids)
                or not (set(evidence_ids) | belief_ids) <= candidate_ids):
            raise ReflectionValidationError("reflection evidence is invalid")
        state = self.get_or_create_state(world_id, owner_npc_id)
        accepted_cursor = (state.last_reflection_source_created_at, state.last_reflection_source_memory_id)
        if (accepted_cursor[0] is not None and source_cursor is not None and source_cursor <= accepted_cursor):
            return False
        if reserved:
            if state.reflection_attempt_fingerprint != fingerprint or state.reflection_attempt_status == "succeeded":
                return False
        elif not self.reflection_attempt_allowed(world_id, owner_npc_id, fingerprint):
            return False
        if source_cursor is not None:
            # SELECT FOR UPDATE is intentionally not the stale-write guard:
            # SQLite ignores it.  This conditional write claims source progress
            # before any derived row is inserted, and serializes writers on both
            # supported dialects.  A newer committed cursor makes rowcount zero.
            claim_conditions = [
                AgentCognitionState.world_id == world_id,
                AgentCognitionState.owner_npc_id == owner_npc_id,
                or_(AgentCognitionState.last_reflection_source_created_at.is_(None),
                    tuple_(AgentCognitionState.last_reflection_source_created_at,
                        AgentCognitionState.last_reflection_source_memory_id) < source_cursor),
            ]
            if reserved:
                claim_conditions.extend((
                    AgentCognitionState.reflection_attempt_fingerprint == fingerprint,
                    AgentCognitionState.reflection_attempt_status != "succeeded",
                ))
            claimed = self.session.execute(update(AgentCognitionState).where(*claim_conditions).values(
                updated_at=datetime.now(UTC)).execution_options(synchronize_session=False))
            if claimed.rowcount != 1:
                return False
            # Rehydrate after the database-level claim rather than trusting the
            # pre-claim ORM identity map snapshot.
            self.session.expire(state)
            self.session.refresh(state)
            if reserved and (state.reflection_attempt_fingerprint != fingerprint
                             or state.reflection_attempt_status == "succeeded"):
                return False
        world = self.session.scalar(select(WorldState).where(WorldState.id == world_id)
            .with_for_update().execution_options(populate_existing=True))
        evidence = tuple(self.session.scalars(select(Memory).where(Memory.id.in_(candidate_ids))
            .order_by(Memory.id).with_for_update().execution_options(populate_existing=True)))
        if len(evidence) != len(candidate_ids) or any(
            row.world_id != world_id or row.owner_npc_id != owner_npc_id
            or row.lifecycle_state not in {"active", "disputed"}
            or row.occurred_world_version > world.world_version or row.created_world_version > world.world_version
            or row.occurred_clock_tick > world.clock_tick or row.created_clock_tick > world.clock_tick
            for row in evidence):
            raise ReflectionValidationError("reflection evidence is invalid")
        # Current beliefs are also provider-visible private cognition. Lock and
        # validate their source reflections, even when no revision was proposed.
        current_belief_ids = frozenset(map(str, current_belief_ids))
        current_beliefs = tuple(self.session.scalars(select(Belief).where(Belief.id.in_(current_belief_ids))
            .order_by(Belief.id).with_for_update().execution_options(populate_existing=True)))
        if len(current_beliefs) != len(current_belief_ids) or any(
            b.world_id != world_id or b.owner_npc_id != owner_npc_id or b.lifecycle_state != "active"
            or b.created_world_version > world.world_version or b.created_clock_tick > world.clock_tick
            for b in current_beliefs):
            raise ReflectionValidationError("reflection evidence is invalid")
        belief_sources = tuple(self.session.scalars(select(Memory).where(Memory.id.in_(
            {b.source_reflection_memory_id for b in current_beliefs})).order_by(Memory.id)
            .with_for_update().execution_options(populate_existing=True)))
        if len(belief_sources) != len(current_beliefs) or any(
            row.world_id != world_id or row.owner_npc_id != owner_npc_id or row.memory_type != "reflection"
            or row.lifecycle_state not in {"active", "disputed"}
            or row.occurred_world_version > world.world_version or row.created_world_version > world.world_version
            or row.occurred_clock_tick > world.clock_tick or row.created_clock_tick > world.clock_tick
            for row in belief_sources):
            raise ReflectionValidationError("reflection evidence is invalid")
        old_belief = None
        if belief is not None and belief.supersedes_belief_id is not None:
            old_id = str(belief.supersedes_belief_id)
            if old_id not in set(map(str, current_belief_ids)):
                raise ReflectionValidationError("reflection evidence is invalid")
            old_belief = self.session.scalar(select(Belief).where(Belief.id == old_id)
                .with_for_update().execution_options(populate_existing=True))
            if (old_belief is None or old_belief.world_id != world_id or old_belief.owner_npc_id != owner_npc_id
                    or old_belief.lifecycle_state != "active" or old_belief.created_world_version > world.world_version
                    or old_belief.created_clock_tick > world.clock_tick):
                raise ReflectionValidationError("reflection evidence is invalid")
        # Every text the provider saw contributes to the permission boundary,
        # including candidates it chose not to cite and current belief context.
        permission_sources = evidence + belief_sources
        secrecy = max((permission_floor[0], *(row.secrecy for row in permission_sources)), key=("public", "private", "secret").index)
        disclosure = max((permission_floor[1], *(row.disclosure_scope for row in permission_sources)), key=("public", "player_dialogue", "internal_only").index)
        now = datetime.now(UTC)
        memory_id = self.reflection_memory_id(world_id, owner_npc_id, fingerprint)
        self.session.add(Memory(id=memory_id, world_id=world_id, owner_npc_id=owner_npc_id,
            memory_type="reflection", content=draft.insight, safe_summary=draft.insight,
            normalized_content_hash=sha256(draft.insight.encode()).hexdigest(), related_entity_ids_json=[],
            occurred_world_version=world.world_version, created_world_version=world.world_version,
            occurred_clock_tick=world.clock_tick, created_clock_tick=world.clock_tick,
            occurred_world_time=world.time, source_created_at=now, created_at=now,
            importance=max(row.importance for row in evidence), confidence=draft.confidence, emotional_valence=0,
            secrecy=secrecy, disclosure_scope=disclosure, lifecycle_state="active", embedding_status="unavailable", access_count=0))
        self.session.flush()
        self.session.add_all(MemoryEvidence(derived_memory_id=memory_id, evidence_memory_id=id, ordinal=i)
            for i, id in enumerate(evidence_ids))
        if belief is not None:
            belief_id = str(uuid4())
            self.session.add(Belief(id=belief_id, world_id=world_id, owner_npc_id=owner_npc_id,
                statement=belief.statement, safe_summary=belief.safe_summary, confidence=belief.confidence,
                lifecycle_state="active", supersedes_belief_id=old_belief.id if old_belief else None,
                source_reflection_memory_id=memory_id, created_world_version=world.world_version,
                created_clock_tick=world.clock_tick, created_at=now))
            if old_belief:
                old_belief.lifecycle_state = belief.prior_belief_disposition
            self.session.flush()
            for role, ids in (("supporting", belief.supporting_memory_ids), ("contradicting", belief.contradicting_memory_ids)):
                self.session.add_all(BeliefEvidence(belief_id=belief_id, memory_id=str(id), evidence_role=role, ordinal=i)
                    for i, id in enumerate(ids))
        state.reflection_memory_count = 0
        state.reflection_accumulated_importance = 0
        state.reflection_pending_critical = 0
        if source_cursor:
            state.last_reflection_source_created_at, state.last_reflection_source_memory_id = source_cursor
            # Preserve sources projected concurrently while the provider ran.
            remaining = self.session.execute(select(Memory.importance, Observation.is_critical)
                .outerjoin(Observation, Observation.id == Memory.source_observation_id).where(
                    Memory.world_id == world_id, Memory.owner_npc_id == owner_npc_id,
                    Memory.memory_type != "reflection", tuple_(Memory.created_at, Memory.id) > source_cursor)).all()
            state.reflection_memory_count = len(remaining)
            state.reflection_accumulated_importance = sum(row.importance for row in remaining)
            state.reflection_pending_critical = int(any(row.is_critical for row in remaining))
        state.last_reflection_evidence_fingerprint = state.reflection_attempt_fingerprint = fingerprint
        state.reflection_attempt_count = 0
        state.reflection_attempt_status = "succeeded"
        state.updated_at = now
        self.session.flush()
        return True

    def _memory_filters(self, request):
        from backend.app.agents.memory_retrieval import SCOPE_RULES
        rule = SCOPE_RULES[request.scope]
        filters = [Memory.world_id == request.world_id, Memory.owner_npc_id == request.owner_npc_id,
            Memory.occurred_world_version <= request.current_world_version,
            Memory.occurred_clock_tick <= request.current_clock_tick,
            Memory.created_world_version <= request.current_world_version,
            Memory.created_clock_tick <= request.current_clock_tick,
            Memory.memory_type.in_(request.allowed_memory_types), Memory.secrecy.in_(rule.secrecy),
            Memory.disclosure_scope.in_(rule.disclosure), Memory.lifecycle_state.in_(rule.lifecycle)]
        if request.excluded_turn_ids:
            filters.append(or_(Observation.source_turn_id.is_(None), Observation.source_turn_id.not_in(request.excluded_turn_ids)))
        if request.conversation_message_upper is not None:
            filters.append(or_(Memory.source_observation_id.is_(None),
                Observation.source_kind != "conversation_turn",
                Observation.source_assistant_message_id <= request.conversation_message_upper))
        if request.created_before is not None:
            filters.append(or_(Memory.memory_type != "reflection", Memory.created_at <= request.created_before))
        return filters

    def allowed_memories(self, request):
        return tuple(self.session.execute(select(Memory, Observation.source_turn_id)
            .outerjoin(Observation, Observation.id == Memory.source_observation_id)
            .where(*self._memory_filters(request)).order_by(Memory.id)).all())

    def semantic_scores(self, request, query, *, expected_hashes):
        if self.session.get_bind().dialect.name != "postgresql":
            return None
        distance = Memory.embedding.op("<=>", return_type=Float)(cast(bindparam("query_vector", type_=String), Vector()))
        statement = select(Memory.id, distance.label("distance")).outerjoin(
            Observation, Observation.id == Memory.source_observation_id).where(
            *self._memory_filters(request),
            tuple_(Memory.id, Memory.embedding_input_hash).in_(bindparam("expected_memory_inputs", expanding=True)),
            Memory.embedding_status == "ready",
            Memory.embedding.is_not(None), Memory.embedding_input_hash.is_not(None),
            Memory.embedding_provider == query.provider, Memory.embedding_model == query.model,
            Memory.embedding_version == query.version, Memory.embedding_dimensions == query.dimensions)
        return {id: max(0.0, min(1.0, 1 - float(distance))) for id, distance in self.session.execute(
            statement, {"query_vector": json.dumps(list(query.vector)),
                "expected_memory_inputs": sorted(expected_hashes.items())})}

    def record_access(self, memory_ids):
        if memory_ids:
            self.session.execute(update(Memory).where(Memory.id.in_(memory_ids)).values(
                access_count=Memory.access_count + 1, last_accessed_at=datetime.now(UTC)))

    def get_or_create_state(self, world_id: str, owner_npc_id: str) -> AgentCognitionState:
        if self.session.get(WorldState, world_id) is None or self.session.get(NpcProfile, owner_npc_id) is None:
            raise ValueError("cognition owner unavailable")
        state = self.session.scalar(select(AgentCognitionState).where(
            AgentCognitionState.world_id == world_id,
            AgentCognitionState.owner_npc_id == owner_npc_id)
            .with_for_update().execution_options(populate_existing=True))
        if state is None:
            state = AgentCognitionState(world_id=world_id, owner_npc_id=owner_npc_id)
            self.session.add(state)
            self.session.flush()
        return state

    def load_source_batch(self, state: AgentCognitionState, *, event_limit: int, turn_limit: int,
                          message_upper_bound: int | None = None) -> SourceBatch:
        if not 1 <= event_limit <= 100 or not 1 <= turn_limit <= 100:
            raise ValueError("invalid cognition batch size")
        events = tuple(self.session.scalars(select(Event).where(
            Event.world_id == state.world_id, Event.event_sequence > state.last_event_sequence
        ).order_by(Event.event_sequence, Event.id).limit(event_limit)))
        # Group complete turns before LIMIT so user/assistant pairs never split.
        # Each legacy NULL turn is its own scanned source, keeping legacy scans bounded.
        legacy_key = case((ConversationMessage.turn_id.is_(None), ConversationMessage.id), else_=0)
        upper = func.max(ConversationMessage.id)
        having = [upper > state.last_conversation_message_id]
        if message_upper_bound is not None:
            having.append(upper <= message_upper_bound)
        groups = self.session.execute(select(
            ConversationMessage.conversation_id, ConversationMessage.turn_id, upper.label("upper")
        ).join(Conversation, Conversation.id == ConversationMessage.conversation_id).where(
            Conversation.world_id == state.world_id, Conversation.npc_id == state.owner_npc_id
        ).group_by(ConversationMessage.conversation_id, ConversationMessage.turn_id, legacy_key)
         .having(*having).order_by(upper).limit(turn_limit)).all()
        turns = []
        for conversation_id, turn_id, message_upper in groups:
            query = select(ConversationMessage).where(ConversationMessage.conversation_id == conversation_id)
            query = query.where(ConversationMessage.id == message_upper) if turn_id is None else query.where(ConversationMessage.turn_id == turn_id)
            turns.append(ConversationTurn(self.session.get(Conversation, conversation_id),
                tuple(self.session.scalars(query.order_by(ConversationMessage.id)))))
        batch = SourceBatch(events=events, turns=tuple(turns),
            npc_profiles=(self.session.get(NpcProfile, state.owner_npc_id),),
            event_upper=events[-1].event_sequence if events else state.last_event_sequence,
            message_upper=groups[-1].upper if groups else state.last_conversation_message_id)
        self._batches[(state.world_id, state.owner_npc_id)] = batch
        return batch

    def persist_core_projection(self, state: AgentCognitionState, drafts: tuple[ObservationDraft, ...]) -> ProjectionResult:
        batch = self._batches.get((state.world_id, state.owner_npc_id))
        if batch is None:
            raise ValueError("cognition source unavailable")
        registry = PerceptionPolicyRegistry()
        sources = {}
        permitted = {}
        for source in batch.events:
            for draft in registry.project_event(source, batch.npc_profiles):
                sources[draft.source_key] = source
                permitted[draft.source_key] = draft
        for turn in batch.turns:
            for draft in registry.project_turn(turn, batch.npc_profiles):
                sources[draft.source_key] = turn
                permitted[draft.source_key] = draft
        # Validate the entire input before any write: source, owner and policy
        # content cannot be replaced by a caller-provided claim or foreign ID.
        if any(draft.owner_npc_id != state.owner_npc_id or permitted.get(draft.source_key) != draft for draft in drafts):
            raise ValueError("cognition source unavailable")
        world = self.session.get(WorldState, state.world_id, populate_existing=True)
        created = 0
        for draft in drafts:
            existing = self.session.scalar(select(Observation.id).where(
                Observation.world_id == state.world_id, Observation.owner_npc_id == state.owner_npc_id,
                Observation.source_key == draft.source_key, Observation.policy_version == draft.policy_version))
            if existing is not None:
                continue
            identity = json.dumps([state.world_id, state.owner_npc_id, draft.source_key, draft.policy_version], separators=(",", ":"))
            observation_id = str(uuid5(NAMESPACE_URL, "aleria:observation:" + identity))
            memory_id = str(uuid5(NAMESPACE_URL, "aleria:memory:" + identity))
            source = sources[draft.source_key]
            references = {}
            if draft.source_kind == SourceKind.EVENT:
                references["source_event_id"] = source.id
                occurred = source
            else:
                user = next(m for m in source.messages if m.role == "user")
                assistant = next(m for m in source.messages if m.role == "assistant")
                references = dict(source_turn_id=user.turn_id, source_user_message_id=user.id,
                                  source_assistant_message_id=assistant.id)
                occurred = user
            facts = to_json_compatible(draft.facts)
            occurrence = dict(occurred_world_version=occurred.world_version,
                occurred_clock_tick=occurred.clock_tick, occurred_world_time=occurred.world_time,
                source_created_at=occurred.created_at)
            self.session.add(Observation(id=observation_id, world_id=state.world_id,
                owner_npc_id=state.owner_npc_id, source_kind=draft.source_kind.value,
                source_key=draft.source_key, policy_version=draft.policy_version, **references, **occurrence,
                perception_mode=draft.perception_mode.value, facts_json=facts,
                related_entity_ids_json=list(draft.related_entity_ids), summary=draft.summary,
                secrecy=draft.secrecy, disclosure_scope=draft.disclosure_scope,
                lifecycle_state="active", is_critical=int(draft.is_critical)))
            self.session.flush()
            content = json.dumps(facts, ensure_ascii=False, sort_keys=True)
            self.session.add(Memory(id=memory_id, world_id=state.world_id, owner_npc_id=state.owner_npc_id,
                memory_type="episodic" if draft.source_kind == SourceKind.EVENT else "conversation",
                source_observation_id=observation_id, content=content, safe_summary=draft.summary,
                normalized_content_hash=sha256(content.encode("utf-8")).hexdigest(),
                related_entity_ids_json=list(draft.related_entity_ids), **occurrence,
                created_world_version=world.world_version, created_clock_tick=world.clock_tick,
                importance=draft.importance, confidence=draft.confidence, emotional_valence=draft.emotional_valence,
                secrecy=draft.secrecy, disclosure_scope=draft.disclosure_scope, lifecycle_state="active",
                embedding_status="unavailable", access_count=0))
            state.reflection_accumulated_importance += draft.importance
            state.reflection_memory_count += 1
            if draft.is_critical:
                state.reflection_pending_critical = 1
            created += 1
        state.last_event_sequence = batch.event_upper
        state.last_conversation_message_id = batch.message_upper
        state.updated_at = datetime.now(UTC)
        self.session.flush()
        return ProjectionResult(created, created)

    def list_npc_ids(self, world_id: str) -> tuple[str, ...]:
        if self.session.get(WorldState, world_id) is None:
            return ()
        return tuple(self.session.scalars(select(NpcProfile.id).order_by(NpcProfile.sort_order, NpcProfile.id)))
