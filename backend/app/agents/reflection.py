"""Evidence-bound reflection, isolated from authoritative world transitions."""
from hashlib import sha256
import logging
import time

from backend.app.core.config import Settings
from backend.app.agents.cognition_contracts import ReflectionDraft
from backend.app.agents.memory_retrieval import RetrievalRequest, RetrievalScope, MemoryType
from backend.app.llm.reflection_provider import ReflectionRequest, ReflectionCandidate

logger = logging.getLogger(__name__)


def evidence_fingerprint(memory_ids) -> str:
    return sha256("\n".join(sorted(set(map(str, memory_ids)))).encode()).hexdigest()


class ReflectionValidationError(ValueError):
    pass


class ReflectionEngine:
    def __init__(self, repository, retriever, provider, *, settings: Settings | None = None):
        self.repository, self.retriever, self.provider = repository, retriever, provider
        self.settings = settings or Settings()

    def is_due(self, state) -> bool:
        return bool(state.reflection_pending_critical or (
            state.reflection_accumulated_importance >= self.settings.reflection_importance_threshold
            and state.reflection_memory_count >= self.settings.reflection_min_new_memories))

    def should_attempt(self, fingerprint: str, *, failed_attempts: int) -> bool:
        return bool(fingerprint) and failed_attempts < 2

    def enrich_if_due(self, world_id: str, owner_npc_id: str, *, deadline=None, monotonic=time.monotonic) -> bool:
        session = self.repository.session
        if session.in_transaction():
            raise ReflectionValidationError("reflection unavailable")
        fingerprint = None
        reserved = False
        try:
            if deadline is not None and monotonic() >= deadline:
                return False
            with session.begin():
                context = self.repository.reflection_context(world_id, owner_npc_id)
            if not self.is_due(context):
                return False
            if deadline is not None and monotonic() >= deadline:
                return False
            # Keep the evidence DAG rooted in sources: derived reflections are
            # never fed back as new source material or trigger contributions.
            retrieval = self.retriever.retrieve_reflection(RetrievalRequest(world_id=world_id, owner_npc_id=owner_npc_id,
                current_world_version=context.current_world_version, current_clock_tick=context.current_clock_tick,
                query_text="", scope=RetrievalScope.INTERNAL_REFLECTION,
                allowed_memory_types=frozenset({MemoryType.EPISODIC, MemoryType.CONVERSATION, MemoryType.KNOWLEDGE}),
                limit=min(12, self.settings.reflection_memory_limit), char_budget=min(8000, self.settings.reflection_char_budget)),
                source_cursor=context.source_cursor)
            if not retrieval.memories:
                return False
            candidate_ids = frozenset(item.memory_id for item in retrieval.memories)
            fingerprint = evidence_fingerprint(candidate_ids)
            if (context.reflection_attempt_fingerprint == fingerprint
                    and not self.should_attempt(fingerprint, failed_attempts=context.reflection_attempt_count)):
                return False
            remaining = self.settings.reflection_timeout_seconds
            if deadline is not None:
                remaining = min(remaining, deadline - monotonic())
                if remaining <= 0:
                    return False
            # Candidate text and current-belief text share the same configured
            # character budget; oversized beliefs are omitted deterministically.
            used = sum(len(item.content) for item in retrieval.memories)
            current_beliefs = []
            for belief in context.current_beliefs:
                if used + len(belief.statement) <= self.settings.reflection_char_budget:
                    current_beliefs.append(belief)
                    used += len(belief.statement)
            request = ReflectionRequest(candidates=tuple(ReflectionCandidate(memory_id=item.memory_id,
                content=item.content, source_label=item.source_label) for item in retrieval.memories),
                current_beliefs=tuple(current_beliefs), timeout_seconds=remaining)
            with session.begin():
                permission_floor = self.repository.reflection_permission_floor(request)
            if deadline is not None:
                remaining = min(self.settings.reflection_timeout_seconds, deadline - monotonic())
                if remaining <= 0:
                    return False
                request = request.model_copy(update={"timeout_seconds": remaining})
            with session.begin():
                reserved = self.repository.reserve_reflection_attempt(world_id, owner_npc_id, fingerprint, context.source_cursor)
            if not reserved:
                return False
            if deadline is not None:
                remaining = min(self.settings.reflection_timeout_seconds, deadline - monotonic())
                if remaining <= 0:
                    return False
                request = request.model_copy(update={"timeout_seconds": remaining})
            draft = ReflectionDraft.model_validate(self.provider.reflect(request))
            if not set(map(str, draft.evidence_memory_ids)) <= candidate_ids:
                raise ReflectionValidationError("reflection evidence is invalid")
            if deadline is not None and monotonic() >= deadline:
                raise TimeoutError("reflection unavailable")
            with session.begin():
                return self.repository.persist_reflection(world_id, owner_npc_id, draft,
                    candidate_ids=candidate_ids, current_belief_ids=tuple(b.belief_id for b in request.current_beliefs),
                    fingerprint=fingerprint, source_cursor=context.source_cursor, permission_floor=permission_floor, reserved=True)
        except Exception:
            session.rollback()
            logger.warning("Reflection unavailable category=reflection_enrichment")
            if fingerprint is not None and reserved:
                try:
                    with session.begin():
                        self.repository.record_reflection_failure(world_id, owner_npc_id, fingerprint)
                except Exception:
                    session.rollback()
                    logger.warning("Reflection state unavailable category=reflection_state")
            return False
