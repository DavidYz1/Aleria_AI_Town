"""Bounded, best-effort projection after the authoritative source commit."""
from collections.abc import Callable
from hashlib import sha256
import logging
import time
from threading import Lock
from weakref import WeakKeyDictionary

from sqlalchemy import select

from backend.app.agents.perception import PerceptionPolicyRegistry
from backend.app.core.config import Settings, get_settings
from backend.app.database.cognition_repository import CognitionRepository, ProjectionResult
from backend.app.database.models import Memory
from backend.app.agents.memory_retrieval import memory_text
from backend.app.agents.reflection import ReflectionEngine
from backend.app.llm.embedding_provider import EmbeddingProvider, normalize, unit_vector

logger = logging.getLogger(__name__)


class EmbeddingEnrichmentService:
    # Request-scoped services share only a scheduling cursor, never Sessions or
    # source data. Weak Engine keys allow disposed application instances to die.
    _retry_cursors = WeakKeyDictionary()
    _retry_lock = Lock()

    def __init__(self, repository: CognitionRepository, provider: EmbeddingProvider):
        self.repository, self.provider = repository, provider

    def enrich_pending(self, world_id: str, owner_npc_id: str, limit: int, *,
                       deadline: float | None = None, monotonic: Callable[[], float] = time.monotonic) -> int:
        session = self.repository.session
        if session.in_transaction() or not 1 <= limit <= 50:
            raise CognitionProjectionError("cognition enrichment unavailable")
        completed = 0
        try:
            if deadline is not None and monotonic() >= deadline:
                return completed
            space = (self.provider.provider, self.provider.model, self.provider.version, self.provider.dimensions)
            rows = session.scalars(select(Memory).where(Memory.world_id == world_id,
                Memory.owner_npc_id == owner_npc_id).order_by(Memory.created_at, Memory.id))
            pending, retry = [], []
            for row in rows:
                content = normalize(memory_text(row))
                digest = sha256(content.encode()).hexdigest()
                if (row.embedding_status == "ready" and row.embedding is not None
                    and (row.embedding_provider, row.embedding_model, row.embedding_version, row.embedding_dimensions) == space
                    and row.embedding_input_hash == digest):
                    continue
                (retry if row.embedding_status == "failed" else pending).append((row.id, content, digest))
            bind = session.get_bind()
            retry_key = (world_id, owner_npc_id, *space)
            with self._retry_lock:
                cursor = self._retry_cursors.get(bind, {}).get(retry_key, "")
            retry.sort(key=lambda item: (item[0] <= cursor, item[0]))
            retry_ids = {item[0] for item in retry}
            pending = (pending + retry)[:limit]
            session.rollback()  # release read transaction before calling the provider
            for id, content, digest in pending:
                remaining = None
                if deadline is not None:
                    remaining = deadline - monotonic()
                    if remaining <= 0:
                        break
                if id in retry_ids:
                    with self._retry_lock:
                        self._retry_cursors.setdefault(bind, {})[retry_key] = id
                result = None
                try:
                    result = (
                        self.provider.embed(content)
                        if remaining is None
                        else self.provider.embed(content, timeout_seconds=remaining)
                    )
                    unit_vector(list(result.vector), space[3])
                    if (result.provider, result.model, result.version, result.dimensions) != space or result.input_hash != digest:
                        raise ValueError("embedding metadata unavailable")
                except Exception:
                    result = None
                    logger.warning("Embedding enrichment unavailable category=embedding_enrichment")
                if deadline is not None and monotonic() >= deadline:
                    # Once the shared budget is exhausted, enrichment performs
                    # no success or failure persistence for this candidate.
                    continue
                try:
                    row = session.scalar(select(Memory).where(Memory.id == id, Memory.world_id == world_id,
                        Memory.owner_npc_id == owner_npc_id).with_for_update().execution_options(populate_existing=True))
                    if row is None or sha256(normalize(memory_text(row)).encode()).hexdigest() != digest:
                        session.rollback()
                        continue
                    if result is None:
                        row.embedding_status = "failed"
                    else:
                        row.embedding = list(result.vector)
                        row.embedding_provider, row.embedding_model, row.embedding_version, row.embedding_dimensions = space
                        row.embedding_input_hash = digest
                        row.embedding_status = "ready"
                    session.commit()
                    completed += int(result is not None)
                except Exception:
                    session.rollback()
                    logger.warning("Embedding persistence unavailable category=embedding_enrichment")
            return completed
        except Exception:
            session.rollback()
            logger.warning("Embedding enrichment unavailable category=embedding_enrichment")
            return completed


class CognitionProjectionError(RuntimeError):
    pass


class CognitionProjectionService:
    def __init__(self, repository: CognitionRepository, *, settings: Settings | None = None,
                 monotonic: Callable[[], float] | None = None,
                 enrichment: EmbeddingEnrichmentService | None = None,
                 reflection: ReflectionEngine | None = None):
        self.repository = repository
        self.settings = settings or get_settings()
        self.monotonic = monotonic or time.monotonic
        self.registry = PerceptionPolicyRegistry()
        self.enrichment = enrichment
        self.reflection = reflection

    def catch_up_owner(self, world_id: str, owner_npc_id: str, *,
                       message_upper_bound: int | None = None,
                       include_enrichment: bool = True) -> ProjectionResult:
        self._require_fresh_session()
        deadline = self.monotonic() + self.settings.cognition_post_commit_budget_seconds
        return self._catch_up_owner(world_id, owner_npc_id, deadline,
            message_upper_bound=message_upper_bound, include_enrichment=include_enrichment)

    def catch_up_world(self, world_id: str) -> ProjectionResult:
        self._require_fresh_session()
        deadline = self.monotonic() + self.settings.cognition_post_commit_budget_seconds
        if self.monotonic() >= deadline:
            return ProjectionResult()
        try:
            owners = self.repository.list_npc_ids(world_id)
        except Exception:
            self._rollback()
            raise CognitionProjectionError("cognition projection unavailable") from None
        observations = memories = 0
        failed = False
        for owner in owners:
            if self.monotonic() >= deadline:
                break
            try:
                result = self._catch_up_owner(world_id, owner, deadline)
                observations += result.created_observations
                memories += result.created_memories
            except CognitionProjectionError:
                failed = True
        # Listing owners may be the only work performed (empty world/deadline).
        # Close only the read transaction this call itself opened.
        if self.repository.session.in_transaction():
            self._rollback()
        if failed:
            raise CognitionProjectionError("cognition projection unavailable") from None
        return ProjectionResult(observations, memories)

    def _require_fresh_session(self) -> None:
        # An existing transaction may contain flushed ORM or Core SQL writes
        # that new/dirty/deleted cannot reveal. Never adopt or roll it back.
        # Production uses a distinct request-scoped cognition Session.
        if self.repository.session.in_transaction():
            raise CognitionProjectionError("cognition projection unavailable")

    def _rollback(self) -> None:
        try:
            self.repository.session.rollback()
        except Exception:
            raise CognitionProjectionError("cognition projection unavailable") from None

    def _catch_up_owner(self, world_id: str, owner_npc_id: str, deadline: float, *,
                        message_upper_bound: int | None = None,
                        include_enrichment: bool = True) -> ProjectionResult:
        if self.monotonic() >= deadline:
            return ProjectionResult()
        session = self.repository.session
        try:
            state = self.repository.get_or_create_state(world_id, owner_npc_id)
            if self.monotonic() >= deadline:
                session.rollback()
                return ProjectionResult()
            batch = self.repository.load_source_batch(state,
                event_limit=self.settings.cognition_source_batch_size,
                turn_limit=self.settings.cognition_source_batch_size,
                message_upper_bound=message_upper_bound)
            drafts = self.registry.project_batch(batch.events, batch.turns, batch.npc_profiles,
                attention_budget=self.settings.cognition_attention_budget)
            result = self.repository.persist_core_projection(state, drafts)
            session.commit()
            if include_enrichment and self.enrichment is not None:
                try:
                    self.enrichment.enrich_pending(world_id, owner_npc_id, self.settings.cognition_enrichment_batch_size,
                        deadline=deadline, monotonic=self.monotonic)
                except Exception:
                    logger.warning("Embedding enrichment unavailable category=embedding_enrichment")
            if include_enrichment and self.reflection is not None and self.monotonic() < deadline:
                try:
                    self.reflection.enrich_if_due(world_id, owner_npc_id, deadline=deadline, monotonic=self.monotonic)
                except Exception:
                    logger.warning("Reflection enrichment unavailable category=reflection_enrichment")
            return result
        except Exception:
            self._rollback()
            raise CognitionProjectionError("cognition projection unavailable") from None
