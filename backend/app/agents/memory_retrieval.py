"""Permission-first, deterministic hybrid retrieval with lexical degradation."""
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
import json
import logging

from backend.app.llm.embedding_provider import EmbeddingProvider, features, normalize, unit_vector

logger = logging.getLogger(__name__)


class MemoryType(StrEnum):
    EPISODIC = "episodic"
    CONVERSATION = "conversation"
    REFLECTION = "reflection"
    KNOWLEDGE = "knowledge"


class RetrievalScope(StrEnum):
    PLAYER_DIALOGUE = "player_dialogue"
    INTERNAL_REFLECTION = "internal_reflection"
    PUBLIC_EXPLANATION = "public_explanation"


@dataclass(frozen=True)
class ScopeRule:
    secrecy: frozenset[str]
    disclosure: frozenset[str]
    lifecycle: frozenset[str]


SCOPE_RULES = {
    RetrievalScope.PLAYER_DIALOGUE: ScopeRule(frozenset({"public", "private"}), frozenset({"public", "player_dialogue"}), frozenset({"active", "disputed"})),
    RetrievalScope.INTERNAL_REFLECTION: ScopeRule(frozenset({"public", "private", "secret"}), frozenset({"public", "player_dialogue", "internal_only"}), frozenset({"active", "disputed"})),
    RetrievalScope.PUBLIC_EXPLANATION: ScopeRule(frozenset({"public"}), frozenset({"public"}), frozenset({"active", "disputed"})),
}


@dataclass(frozen=True)
class RetrievalRequest:
    world_id: str
    owner_npc_id: str
    current_world_version: int
    current_clock_tick: int
    query_text: str
    scope: RetrievalScope
    allowed_memory_types: frozenset[MemoryType]
    limit: int
    char_budget: int
    excluded_turn_ids: frozenset[str] = frozenset()
    conversation_message_upper: int | None = None
    created_before: datetime | None = None

    def __post_init__(self):
        if self.scope not in SCOPE_RULES or not 1 <= self.limit <= 50 or not 1 <= self.char_budget <= 8000:
            raise ValueError("invalid retrieval request")


@dataclass(frozen=True)
class RetrievedMemory:
    memory_id: str
    memory_type: str
    source_label: str
    content: str
    occurred_clock_tick: int
    source_turn_id: str | None
    source_observation_id: str | None
    score: float
    semantic: float
    lexical: float
    recency: float
    importance: float
    confidence: float


@dataclass(frozen=True)
class RetrievalResult:
    memories: tuple[RetrievedMemory, ...]
    mode: str
    error_code: str | None = None
    scoring_version: str = "hybrid-v1"

    @property
    def memory_ids(self) -> tuple[str, ...]:
        return tuple(item.memory_id for item in self.memories)


class MemoryRetrievalError(RuntimeError):
    pass


def memory_text(memory, scope=RetrievalScope.INTERNAL_REFLECTION) -> str:
    # Only call after the repository's owner/disclosure boundary. The public
    # explanation surface never exposes private source payloads.
    if memory.memory_type == "conversation" and scope != RetrievalScope.PUBLIC_EXPLANATION:
        try:
            claim = json.loads(memory.content).get("claim_text")
            if isinstance(claim, str):
                return claim
        except (ValueError, TypeError, AttributeError):
            pass
    return memory.safe_summary


def compatible(memory, query, scope: RetrievalScope) -> bool:
    return (memory.embedding_status == "ready" and memory.embedding is not None
        and (memory.embedding_provider, memory.embedding_model, memory.embedding_version, memory.embedding_dimensions)
        == (query.provider, query.model, query.version, query.dimensions)
        and memory.embedding_input_hash == sha256(normalize(memory_text(memory, scope)).encode()).hexdigest())


def cosine(memory, query) -> float:
    vector = unit_vector(list(memory.embedding), query.dimensions)
    return max(0.0, min(1.0, sum(a*b for a, b in zip(vector, query.vector))))


class MemoryRetriever:
    def __init__(self, repository, provider: EmbeddingProvider, *, semantic_scorer=None):
        self.repository, self.provider = repository, provider
        self.semantic_scorer = semantic_scorer or cosine

    def retrieve_reflection(self, request: RetrievalRequest, *, source_cursor) -> RetrievalResult:
        """Empty-query source selection performs no external embedding calls.

        A fixed creation-order scan makes retry fingerprints independent of
        model availability, telemetry and the current world's moving clock.
        """
        session = self.repository.session
        if session.in_transaction() or request.scope != RetrievalScope.INTERNAL_REFLECTION or request.query_text:
            raise MemoryRetrievalError("memory unavailable")
        labels = {"knowledge": "authored_knowledge", "episodic": "observed_event", "conversation": "player_claim"}
        chosen, used = [], 0
        try:
            with session.begin():
                for memory in self.repository.reflection_candidate_rows(request, source_cursor):
                    content = memory_text(memory, request.scope)
                    if used + len(content) > request.char_budget:
                        continue
                    chosen.append(RetrievedMemory(memory.id, memory.memory_type, labels[memory.memory_type], content,
                        memory.occurred_clock_tick, None, memory.source_observation_id, 0, 0, 0, 0,
                        memory.importance, memory.confidence))
                    used += len(content)
                    if len(chosen) == request.limit:
                        break
            return RetrievalResult(tuple(chosen), "lexical_fallback", scoring_version="reflection-source-v1")
        except Exception:
            session.rollback()
            raise MemoryRetrievalError("memory unavailable") from None

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        session = self.repository.session
        if session.in_transaction():
            raise MemoryRetrievalError("memory unavailable")
        try:
            mode, error_code, scores = "hybrid", None, {}
            has_allowed_candidates = bool(self.repository.allowed_memories(request))
            session.rollback()
            query = None
            if has_allowed_candidates:
                try:
                    query = self.provider.embed(request.query_text)
                except Exception:
                    mode, error_code = "lexical_fallback", "embedding_unavailable"
            else:
                mode, error_code, scores = "lexical_fallback", "embedding_unavailable", {}
            # Authorization and lifecycle are mutable internal state. Reapply
            # the complete SQL hard filter after external provider work.
            rows = self.repository.allowed_memories(request)
            if query is not None:
                try:
                    expected_hashes = {memory.id: memory.embedding_input_hash for memory, _ in rows
                        if compatible(memory, query, request.scope)}
                    # Savepoint lets failed pgvector SQL degrade without reusing an
                    # aborted PostgreSQL transaction or broadening the candidate set.
                    with session.begin_nested():
                        pg_scores = self.repository.semantic_scores(request, query, expected_hashes=expected_hashes)
                    for memory, _ in rows:
                        if memory.id in expected_hashes:
                            if pg_scores is None:
                                scores[memory.id] = self.semantic_scorer(memory, query)
                            elif memory.id in pg_scores:
                                scores[memory.id] = pg_scores[memory.id]
                    if not scores:
                        mode, error_code = "lexical_fallback", "embedding_unavailable"
                except Exception:
                    mode, error_code, scores = "lexical_fallback", "embedding_unavailable", {}
            query_tokens = set(features(request.query_text))
            ranked = []
            labels = {"knowledge": "authored_knowledge", "episodic": "observed_event", "conversation": "player_claim", "reflection": "reflection"}
            for memory, turn_id in rows:
                content = memory_text(memory, request.scope)
                lexical = len(query_tokens.intersection(features(content))) / len(query_tokens) if query_tokens else 0.0
                recency = .95 ** max(0, request.current_clock_tick - memory.occurred_clock_tick)
                semantic = scores.get(memory.id, 0.0)
                if mode == "hybrid" and memory.id in scores:
                    score = .40 * semantic + .20 * lexical + .20 * recency + .15 * memory.importance + .05 * memory.confidence
                else:
                    score = .45 * lexical + .25 * recency + .20 * memory.importance + .10 * memory.confidence
                score *= .85 if memory.lifecycle_state == "disputed" else 1
                ranked.append(RetrievedMemory(memory.id, memory.memory_type, labels[memory.memory_type], content,
                    memory.occurred_clock_tick, turn_id, memory.source_observation_id, score,
                    semantic, lexical, recency, memory.importance, memory.confidence))
            chosen, used = [], 0
            for item in sorted(ranked, key=lambda item: (-item.score, item.memory_id)):
                if used + len(item.content) > request.char_budget:
                    continue
                chosen.append(item)
                used += len(item.content)
                if len(chosen) == request.limit:
                    break
            result = RetrievalResult(tuple(chosen), mode, error_code)
            if request.scope != RetrievalScope.PUBLIC_EXPLANATION:
                try:
                    self.repository.record_access(result.memory_ids)
                    session.commit()
                except Exception:
                    session.rollback()
                    logger.warning("Memory telemetry unavailable category=access_telemetry")
            else:
                session.rollback()
            return result
        except Exception:
            try:
                session.rollback()
            except Exception:
                pass
            raise MemoryRetrievalError("memory unavailable") from None
