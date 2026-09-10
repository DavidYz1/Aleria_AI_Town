"""Owner-scoped core projection. The caller owns commit/rollback."""
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
import json
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from backend.app.agents.cognition_contracts import ObservationDraft, SourceKind
from backend.app.agents.contracts import to_json_compatible
from backend.app.agents.perception import PerceptionPolicyRegistry
from backend.app.database.models import (
    AgentCognitionState, Conversation, ConversationMessage, Event, Memory,
    NpcProfile, Observation, WorldState,
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

    def load_source_batch(self, state: AgentCognitionState, *, event_limit: int, turn_limit: int) -> SourceBatch:
        if not 1 <= event_limit <= 100 or not 1 <= turn_limit <= 100:
            raise ValueError("invalid cognition batch size")
        events = tuple(self.session.scalars(select(Event).where(
            Event.world_id == state.world_id, Event.event_sequence > state.last_event_sequence
        ).order_by(Event.event_sequence, Event.id).limit(event_limit)))
        # Group complete turns before LIMIT so user/assistant pairs never split.
        # Each legacy NULL turn is its own scanned source, keeping legacy scans bounded.
        legacy_key = case((ConversationMessage.turn_id.is_(None), ConversationMessage.id), else_=0)
        upper = func.max(ConversationMessage.id)
        groups = self.session.execute(select(
            ConversationMessage.conversation_id, ConversationMessage.turn_id, upper.label("upper")
        ).join(Conversation, Conversation.id == ConversationMessage.conversation_id).where(
            Conversation.world_id == state.world_id, Conversation.npc_id == state.owner_npc_id
        ).group_by(ConversationMessage.conversation_id, ConversationMessage.turn_id, legacy_key)
         .having(upper > state.last_conversation_message_id).order_by(upper).limit(turn_limit)).all()
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
