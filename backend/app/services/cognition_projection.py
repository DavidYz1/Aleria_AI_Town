"""Bounded, best-effort projection after the authoritative source commit."""
from collections.abc import Callable
import time

from backend.app.agents.perception import PerceptionPolicyRegistry
from backend.app.core.config import Settings, get_settings
from backend.app.database.cognition_repository import CognitionRepository, ProjectionResult


class CognitionProjectionError(RuntimeError):
    pass


class CognitionProjectionService:
    def __init__(self, repository: CognitionRepository, *, settings: Settings | None = None,
                 monotonic: Callable[[], float] | None = None):
        self.repository = repository
        self.settings = settings or get_settings()
        self.monotonic = monotonic or time.monotonic
        self.registry = PerceptionPolicyRegistry()

    def catch_up_owner(self, world_id: str, owner_npc_id: str) -> ProjectionResult:
        self._require_fresh_session()
        deadline = self.monotonic() + self.settings.cognition_post_commit_budget_seconds
        return self._catch_up_owner(world_id, owner_npc_id, deadline)

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

    def _catch_up_owner(self, world_id: str, owner_npc_id: str, deadline: float) -> ProjectionResult:
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
                turn_limit=self.settings.cognition_source_batch_size)
            drafts = self.registry.project_batch(batch.events, batch.turns, batch.npc_profiles,
                attention_budget=self.settings.cognition_attention_budget)
            result = self.repository.persist_core_projection(state, drafts)
            session.commit()
            return result
        except Exception:
            self._rollback()
            raise CognitionProjectionError("cognition projection unavailable") from None
