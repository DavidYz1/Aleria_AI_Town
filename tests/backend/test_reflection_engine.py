"""Real persisted evidence, bounded retries, append-only beliefs and isolation."""
import importlib
from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.exc import SQLAlchemyError

from backend.app.agents.cognition_contracts import ReflectionDraft, BeliefDraft
from backend.app.agents.memory_retrieval import MemoryRetriever
from backend.app.database.cognition_repository import CognitionRepository
from backend.app.database.models import AgentCognitionState, Memory, MemoryEvidence, Belief, BeliefEvidence, WorldState
from backend.app.llm.embedding_provider import DeterministicEmbeddingProvider
from backend.app.llm.reflection_provider import FakeReflectionProvider
from tests.backend.test_memory_retrieval import memory_session, add_memory

WORLD = "retrieval-test-world"
IDS = tuple(str(UUID(int=i)) for i in range(1, 5))


def prepare(session):
    for id in IDS[:3]:
        add_memory(session, id, world_id=WORLD, importance=.8)
    repository = CognitionRepository(session)
    state = repository.get_or_create_state(WORLD, "grey")
    state.reflection_memory_count, state.reflection_accumulated_importance = 3, 2.4
    session.commit()
    return repository


def derived_counts(session):
    return (session.scalar(select(func.count()).select_from(Memory).where(Memory.memory_type == "reflection")),
        *(session.scalar(select(func.count()).select_from(model)) for model in (MemoryEvidence, Belief, BeliefEvidence)))


def authority(session):
    # Every authoritative/graph table is compared, including state payloads, not only counters.
    from backend.app.database.models import Base
    excluded = {"memories", "memory_evidence", "beliefs", "belief_evidence", "observations", "agent_cognition_states"}
    return {table.name: tuple(tuple(row) for row in session.execute(select(table)))
        for table in Base.metadata.sorted_tables if table.name not in excluded}


def engine(session, provider=None, repository=None):
    repo = repository or CognitionRepository(session)
    return api().ReflectionEngine(repo, MemoryRetriever(repo, DeterministicEmbeddingProvider()), provider or FakeReflectionProvider())


class DraftProvider:
    def __init__(self, mutate=None, belief=False):
        self.mutate, self.belief, self.calls, self.requests = mutate, belief, 0, []

    def reflect(self, request):
        self.calls += 1
        self.requests.append(request)
        data = dict(insight="Reflection safe content", confidence=.7, evidence_memory_ids=[IDS[0]],
            provider="fixture", model="fixture", prompt_version="reflection-v1")
        if self.belief:
            data["belief"] = dict(statement="Private belief statement", safe_summary="Tentative view", confidence=.6,
                supporting_memory_ids=[IDS[0]], contradicting_memory_ids=[IDS[1]])
        if self.mutate:
            self.mutate(data, request)
        return data


def test_valid_reflection_is_atomic_authoritative_timed_and_idempotent(memory_session):
    session = memory_session
    prepare(session)
    before = authority(session)
    source = session.scalar(select(Memory).where(Memory.world_id == WORLD).order_by(Memory.created_at.desc(), Memory.id.desc()))
    cursor = source.created_at, source.id
    session.rollback()
    provider = DraftProvider(belief=True)
    assert engine(session, provider).enrich_if_due(WORLD, "grey") is True
    assert not session.in_transaction()
    assert derived_counts(session) == (1, 1, 1, 2)
    reflection = session.scalar(select(Memory).where(Memory.memory_type == "reflection"))
    assert (reflection.occurred_world_version, reflection.created_world_version,
        reflection.occurred_clock_tick, reflection.created_clock_tick, reflection.occurred_world_time) == (7, 7, 9, 9, "09:00")
    state = session.get(AgentCognitionState, (WORLD, "grey"))
    assert (state.reflection_memory_count, state.reflection_accumulated_importance, state.reflection_pending_critical) == (0, 0, 0)
    assert (state.last_reflection_source_created_at, state.last_reflection_source_memory_id) == cursor
    assert state.reflection_attempt_status == "succeeded"
    assert state.last_reflection_evidence_fingerprint == api().evidence_fingerprint(IDS[:3])
    assert authority(session) == before
    # Even artificially re-triggered state must never duplicate a fingerprint.
    state.reflection_pending_critical = 1
    session.commit()
    assert engine(session, provider).enrich_if_due(WORLD, "grey") is False
    assert provider.calls == 1


@pytest.mark.parametrize("kind", ["empty", "invented", "not_candidate", "owner", "world", "future",
    "future_created", "future_tick", "superseded", "confidence", "length", "unknown_belief", "belief_evidence"])
def test_invalid_draft_never_writes_derived_or_changes_authority(memory_session, kind):
    session = memory_session
    prepare(session)
    before = authority(session)
    session.rollback()
    def mutate(data, request):
        assert not session.in_transaction()
        if kind == "empty": data["evidence_memory_ids"] = []
        elif kind == "invented": data["evidence_memory_ids"] = [str(UUID(int=999))]
        elif kind == "not_candidate":
            add_memory(session, IDS[3], world_id=WORLD)
            data["evidence_memory_ids"] = [IDS[3]]
        elif kind in {"owner", "world", "future", "future_created", "future_tick", "superseded"}:
            row = session.get(Memory, IDS[0])
            field, value = {"owner": ("owner_npc_id", "ryan"), "world": ("world_id", "aleria-town"),
                "future": ("occurred_world_version", 8), "future_created": ("created_world_version", 8),
                "future_tick": ("occurred_clock_tick", 10), "superseded": ("lifecycle_state", "superseded")}[kind]
            setattr(row, field, value)
            session.commit()
        elif kind == "confidence": data["confidence"] = 1.1
        elif kind == "length": data["insight"] = "x" * 801
        elif kind == "unknown_belief":
            data["belief"].update(supersedes_belief_id=str(UUID(int=999)), prior_belief_disposition="superseded")
        elif kind == "belief_evidence": data["belief"]["contradicting_memory_ids"] = [str(UUID(int=999))]
    assert engine(session, DraftProvider(mutate, belief=True)).enrich_if_due(WORLD, "grey") is False
    assert not session.in_transaction()
    assert derived_counts(session) == (0, 0, 0, 0)
    assert authority(session) == before
    state = session.get(AgentCognitionState, (WORLD, "grey"))
    assert state.reflection_attempt_count == 1 and state.reflection_attempt_status == "failed"


@pytest.mark.parametrize("failure", ["provider", "database"])
def test_failures_rollback_all_derived_and_retry_once_until_new_evidence(memory_session, failure, caplog):
    session = memory_session
    prepare(session)
    before = authority(session)
    session.rollback()
    def fail(data, request):
        if failure == "provider": raise TimeoutError("SECRET payload")
    provider = DraftProvider(fail, belief=True)
    def fail_flush(session, context, instances):
        if any(isinstance(row, BeliefEvidence) for row in session.new):
            raise SQLAlchemyError("SECRET payload")
    if failure == "database": event.listen(session, "before_flush", fail_flush)
    try:
        for _ in range(3):
            assert engine(session, provider).enrich_if_due(WORLD, "grey") is False
        assert provider.calls == 2
        assert derived_counts(session) == (0, 0, 0, 0)
        assert authority(session) == before
        state = session.get(AgentCognitionState, (WORLD, "grey"))
        assert state.reflection_attempt_count == 2
        session.rollback()
        add_memory(session, IDS[3], world_id=WORLD, importance=1)
        assert engine(session, provider).enrich_if_due(WORLD, "grey") is False
        assert provider.calls == 3
    finally:
        if failure == "database": event.remove(session, "before_flush", fail_flush)
    assert "SECRET" not in caplog.text


@pytest.mark.parametrize("disposition", ["superseded", "disputed"])
def test_belief_revision_appends_preserving_statement_and_evidence(memory_session, disposition):
    session = memory_session
    prepare(session)
    assert engine(session, DraftProvider(belief=True)).enrich_if_due(WORLD, "grey")
    old = session.scalar(select(Belief))
    old_id, old_statement = old.id, old.statement
    old_edges = tuple(session.execute(select(BeliefEvidence.memory_id, BeliefEvidence.evidence_role).where(BeliefEvidence.belief_id == old_id)))
    state = session.get(AgentCognitionState, (WORLD, "grey"))
    state.reflection_pending_critical = 1
    session.commit()
    add_memory(session, IDS[3], world_id=WORLD)
    def revise(data, request):
        assert old_id in {str(b.belief_id) for b in request.current_beliefs}
        data["belief"].update(statement="Revised private belief", supersedes_belief_id=old_id, prior_belief_disposition=disposition)
    assert engine(session, DraftProvider(revise, belief=True)).enrich_if_due(WORLD, "grey")
    session.expire_all()
    old = session.get(Belief, old_id)
    assert old.statement == old_statement and old.lifecycle_state == disposition
    assert tuple(session.execute(select(BeliefEvidence.memory_id, BeliefEvidence.evidence_role).where(BeliefEvidence.belief_id == old_id))) == old_edges
    new = session.scalar(select(Belief).where(Belief.id != old_id))
    assert new.lifecycle_state == "active" and new.supersedes_belief_id == old_id


def test_current_belief_context_is_useful_bounded_and_propagates_source_permissions(memory_session):
    session = memory_session
    prepare(session)
    source = session.get(Memory, IDS[0])
    source.secrecy, source.disclosure_scope = "secret", "internal_only"
    session.commit()
    assert engine(session, DraftProvider(belief=True)).enrich_if_due(WORLD, "grey")
    old = session.scalar(select(Belief))
    old_id = old.id
    # New source evidence is public, but previous belief context was secret.
    source.secrecy, source.disclosure_scope = "public", "public"
    state = session.get(AgentCognitionState, (WORLD, "grey"))
    state.reflection_pending_critical = 1
    session.commit()
    add_memory(session, IDS[3], world_id=WORLD)
    provider = DraftProvider()
    assert engine(session, provider).enrich_if_due(WORLD, "grey")
    current = next(b for b in provider.requests[0].current_beliefs if str(b.belief_id) == old_id)
    assert current.statement == "Private belief statement"
    assert current.confidence == .6 and current.lifecycle_state == "active"
    latest = session.scalar(select(Memory).where(Memory.memory_type == "reflection").order_by(Memory.created_at.desc()))
    assert (latest.secrecy, latest.disclosure_scope) == ("secret", "internal_only")


def test_secret_candidate_cannot_be_laundered_by_omitting_its_citation(memory_session):
    session = memory_session
    prepare(session)
    row = session.get(Memory, IDS[1])
    row.secrecy, row.disclosure_scope = "secret", "internal_only"
    session.commit()
    assert engine(session, DraftProvider()).enrich_if_due(WORLD, "grey")
    reflection = session.scalar(select(Memory).where(Memory.memory_type == "reflection"))
    assert (reflection.secrecy, reflection.disclosure_scope) == ("secret", "internal_only")


def test_permission_change_during_provider_cannot_publish_previously_secret_input(memory_session):
    session = memory_session
    prepare(session)
    row = session.get(Memory, IDS[1])
    row.secrecy, row.disclosure_scope = "secret", "internal_only"
    session.commit()
    def change_permissions(data, request):
        row = session.get(Memory, IDS[1])
        row.secrecy, row.disclosure_scope = "public", "public"
        session.commit()
    engine(session, DraftProvider(change_permissions)).enrich_if_due(WORLD, "grey")
    reflections = tuple(session.scalars(select(Memory).where(Memory.memory_type == "reflection")))
    assert all((row.secrecy, row.disclosure_scope) == ("secret", "internal_only") for row in reflections)


@pytest.mark.parametrize("field,value", [("owner_npc_id", "ryan"), ("world_id", "aleria-town"),
    ("lifecycle_state", "superseded"), ("created_world_version", 8)])
def test_current_belief_changed_during_provider_is_rejected(memory_session, field, value):
    session = memory_session
    prepare(session)
    assert engine(session, DraftProvider(belief=True)).enrich_if_due(WORLD, "grey")
    old_id = session.scalar(select(Belief.id))
    session.get(AgentCognitionState, (WORLD, "grey")).reflection_pending_critical = 1
    session.commit()
    add_memory(session, IDS[3], world_id=WORLD)
    def mutate(data, request):
        setattr(session.get(Belief, old_id), field, value)
        session.commit()
        data["belief"].update(supersedes_belief_id=old_id, prior_belief_disposition="superseded")
    assert not engine(session, DraftProvider(mutate, belief=True)).enrich_if_due(WORLD, "grey")
    assert derived_counts(session) == (1, 1, 1, 2)


def test_engine_rejects_existing_transaction_without_adopting_or_rolling_it_back(memory_session):
    session = memory_session
    prepare(session)
    world = session.get(WorldState, WORLD)
    world.world_version = 10
    transaction = session.get_transaction()
    with pytest.raises(api().ReflectionValidationError):
        engine(session).enrich_if_due(WORLD, "grey")
    assert session.get_transaction() is transaction and world.world_version == 10


def test_provider_deadline_and_input_budget_are_bounded(memory_session):
    from backend.app.core.config import Settings
    session = memory_session
    repo = prepare(session)
    for n in range(4, 22):
        add_memory(session, str(UUID(int=n)), text="x" * 200, world_id=WORLD)
    provider = DraftProvider()
    subject = api().ReflectionEngine(repo, MemoryRetriever(repo, DeterministicEmbeddingProvider()), provider,
        settings=Settings(_env_file=None, reflection_memory_limit=20, reflection_char_budget=500))
    assert subject.enrich_if_due(WORLD, "grey", deadline=1.2, monotonic=lambda: .7)
    request = provider.requests[0]
    assert len(request.candidates) <= 12
    assert sum(len(c.content) for c in request.candidates) + sum(len(b.statement) for b in request.current_beliefs) <= 500
    assert request.timeout_seconds == pytest.approx(.5)


def test_expired_deadline_skips_provider_and_late_result_is_not_persisted(memory_session):
    session = memory_session
    prepare(session)
    provider = DraftProvider()
    assert not engine(session, provider).enrich_if_due(WORLD, "grey", deadline=1, monotonic=lambda: 2)
    assert provider.calls == 0
    now = [0]
    def late(data, request): now[0] = 2
    assert not engine(session, DraftProvider(late)).enrich_if_due(WORLD, "grey", deadline=1, monotonic=lambda: now[0])
    assert derived_counts(session) == (0, 0, 0, 0)


def test_deadline_expired_during_preflight_does_not_start_provider(memory_session):
    session = memory_session
    prepare(session)
    now = [0.0]
    class SlowPreflight(CognitionRepository):
        def reflection_permission_floor(self, request):
            result = super().reflection_permission_floor(request)
            now[0] = 2
            return result
    provider = DraftProvider()
    assert not engine(session, provider, SlowPreflight(session)).enrich_if_due(
        WORLD, "grey", deadline=1, monotonic=lambda: now[0])
    assert provider.calls == 0
    assert derived_counts(session) == (0, 0, 0, 0)


def test_concurrent_source_is_retained_after_success_cursor(memory_session):
    session = memory_session
    prepare(session)
    def new_source(data, request):
        add_memory(session, IDS[3], world_id=WORLD, importance=.9)
    assert engine(session, DraftProvider(new_source)).enrich_if_due(WORLD, "grey")
    state = session.get(AgentCognitionState, (WORLD, "grey"))
    assert state.last_reflection_source_memory_id == IDS[2]
    assert state.reflection_memory_count == 1 and state.reflection_accumulated_importance == pytest.approx(.9)


def test_three_concurrent_sessions_reserve_at_most_two_provider_attempts(memory_session):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier, Event, Lock
    from sqlalchemy.orm import Session
    session = memory_session
    prepare(session)
    start, release, completed, lock = Barrier(4), Event(), Event(), Lock()
    calls = []
    class BlockedProvider:
        def reflect(self, request):
            with lock: calls.append(request)
            assert release.wait(5)
            raise TimeoutError("private provider failure")
    def run():
        with Session(session.bind, expire_on_commit=False) as other:
            start.wait()
            try:
                return engine(other, BlockedProvider()).enrich_if_due(WORLD, "grey")
            finally:
                completed.set()
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(run) for _ in range(3)]
        start.wait()
        try:
            completed.wait(2)
        finally:
            release.set()
        assert [f.result(timeout=5) for f in futures] == [False, False, False]
    assert 1 <= len(calls) <= 2
    state = session.get(AgentCognitionState, (WORLD, "grey"), populate_existing=True)
    assert state.reflection_attempt_count == len(calls)
    assert derived_counts(session) == (0, 0, 0, 0)


def test_candidate_selection_never_calls_embedding_and_stays_stable_across_embedding_availability(memory_session):
    session = memory_session
    repo = prepare(session)
    for n in range(4, 18):
        add_memory(session, str(UUID(int=n)), world_id=WORLD, importance=.9)
    embedding_calls = []
    class ChangingEmbedding(DeterministicEmbeddingProvider):
        available = True
        def embed(self, text):
            embedding_calls.append(text)
            if not self.available: raise TimeoutError("external embedding")
            return super().embed(text)
    provider = DraftProvider(lambda data, request: (_ for _ in ()).throw(TimeoutError("failed")))
    embedding = ChangingEmbedding()
    subject = api().ReflectionEngine(repo, MemoryRetriever(repo, embedding), provider)
    for available in (True, False, True):
        embedding.available = available
        assert not subject.enrich_if_due(WORLD, "grey")
    assert embedding_calls == []
    assert provider.calls == 2
    assert provider.requests[0].candidates == provider.requests[1].candidates
    assert not session.in_transaction()


@pytest.mark.parametrize("older_fails", [False, True])
def test_newer_batch_success_makes_older_completion_stale_without_overwriting_state(memory_session, older_fails):
    from sqlalchemy.orm import Session
    session = memory_session
    prepare(session)
    newer = []
    def finish_newer_first(data, request):
        assert not session.in_transaction()
        with Session(session.bind, expire_on_commit=False) as other:
            add_memory(other, IDS[3], world_id=WORLD, importance=.9)
            assert engine(other, DraftProvider()).enrich_if_due(WORLD, "grey")
            state = other.get(AgentCognitionState, (WORLD, "grey"))
            newer.append((state.last_reflection_source_created_at, state.last_reflection_source_memory_id,
                state.last_reflection_evidence_fingerprint, state.reflection_attempt_fingerprint,
                state.reflection_attempt_status, state.reflection_attempt_count,
                state.reflection_memory_count, state.reflection_accumulated_importance))
        if older_fails:
            raise TimeoutError("older request failed after newer success")
    assert not engine(session, DraftProvider(finish_newer_first)).enrich_if_due(WORLD, "grey")
    state = session.get(AgentCognitionState, (WORLD, "grey"), populate_existing=True)
    assert (state.last_reflection_source_created_at, state.last_reflection_source_memory_id,
        state.last_reflection_evidence_fingerprint, state.reflection_attempt_fingerprint,
        state.reflection_attempt_status, state.reflection_attempt_count,
        state.reflection_memory_count, state.reflection_accumulated_importance) == newer[0]
    assert derived_counts(session) == (1, 1, 0, 0)


def test_persist_that_read_old_sqlite_state_cannot_overwrite_newer_success(memory_session):
    """A stale writer must lose before it can insert any derived cognition."""
    from threading import Event, Thread
    from sqlalchemy.orm import Session

    session = memory_session
    prepare(session)
    source_cursor = session.execute(select(Memory.created_at, Memory.id).where(
        Memory.id.in_(IDS[:3])).order_by(Memory.created_at.desc(), Memory.id.desc()).limit(1)).one()
    session.rollback()
    stale_read, allow_stale = Event(), Event()
    stale_result, stale_error = [], []

    class PauseAfterInitialStateRead(CognitionRepository):
        def __init__(self, *args):
            super().__init__(*args)
            self.paused = False

        def get_or_create_state(self, *args):
            state = super().get_or_create_state(*args)
            if not self.paused:
                self.paused = True
                stale_read.set()
                assert allow_stale.wait(5)
            return state

    def persist_stale_batch():
        with Session(session.bind, expire_on_commit=False) as older:
            try:
                with older.begin():
                    stale_result.append(PauseAfterInitialStateRead(older).persist_reflection(
                        WORLD, "grey", ReflectionDraft(insight="Older reflection", confidence=.7,
                        evidence_memory_ids=(UUID(IDS[0]),), provider="fixture", model="fixture",
                        prompt_version="reflection-v1"), candidate_ids=IDS[:3], current_belief_ids=(),
                        fingerprint=api().evidence_fingerprint(IDS[:3]), source_cursor=source_cursor))
            except Exception as exc:  # surfaced below so the interleaving is never hidden
                stale_error.append(exc)

    older = Thread(target=persist_stale_batch)
    older.start()
    assert stale_read.wait(5)
    with Session(session.bind, expire_on_commit=False) as newer:
        add_memory(newer, IDS[3], world_id=WORLD, importance=.9)
        assert engine(newer, DraftProvider()).enrich_if_due(WORLD, "grey") is True
        newer_state = newer.get(AgentCognitionState, (WORLD, "grey"))
        successful_state = tuple(getattr(newer_state, column.name)
            for column in AgentCognitionState.__table__.columns)
    allow_stale.set()
    older.join(5)
    assert not older.is_alive() and stale_error == []
    assert stale_result == [False]
    with Session(session.bind, expire_on_commit=False) as verify:
        final_state = verify.get(AgentCognitionState, (WORLD, "grey"))
        assert tuple(getattr(final_state, column.name)
            for column in AgentCognitionState.__table__.columns) == successful_state
        assert (final_state.last_reflection_source_created_at,
            final_state.last_reflection_source_memory_id) > source_cursor
        assert final_state.last_reflection_source_memory_id == IDS[3]
        assert derived_counts(verify) == (1, 1, 0, 0)


def test_stale_reserved_batch_cannot_overwrite_newer_reservation(memory_session):
    """A claim must also recheck the reservation it read before a new claim won."""
    from threading import Event, Thread
    from sqlalchemy.orm import Session

    session = memory_session
    prepare(session)
    with Session(session.bind, expire_on_commit=False) as setup:
        repo = CognitionRepository(setup)
        with setup.begin():
            older_context = repo.reflection_context(WORLD, "grey")
        older_fingerprint = api().evidence_fingerprint(IDS[:3])
        with setup.begin():
            assert repo.reserve_reflection_attempt(WORLD, "grey", older_fingerprint, older_context.source_cursor)
    stale_read, allow_stale = Event(), Event()
    stale_result, stale_error = [], []

    class PauseAfterInitialStateRead(CognitionRepository):
        def __init__(self, *args):
            super().__init__(*args)
            self.paused = False

        def get_or_create_state(self, *args):
            state = super().get_or_create_state(*args)
            if not self.paused:
                self.paused = True
                stale_read.set()
                assert allow_stale.wait(5)
            return state

    def persist_stale_reservation():
        with Session(session.bind, expire_on_commit=False) as older:
            try:
                with older.begin():
                    stale_result.append(PauseAfterInitialStateRead(older).persist_reflection(
                        WORLD, "grey", ReflectionDraft(insight="Older reservation", confidence=.7,
                        evidence_memory_ids=(UUID(IDS[0]),), provider="fixture", model="fixture",
                        prompt_version="reflection-v1"), candidate_ids=IDS[:3], current_belief_ids=(),
                        fingerprint=older_fingerprint, source_cursor=older_context.source_cursor, reserved=True))
            except Exception as exc:
                stale_error.append(exc)

    older = Thread(target=persist_stale_reservation)
    older.start()
    assert stale_read.wait(5)
    with Session(session.bind, expire_on_commit=False) as newer:
        add_memory(newer, IDS[3], world_id=WORLD, importance=.9)
        newer_repo = CognitionRepository(newer)
        with newer.begin():
            newer_context = newer_repo.reflection_context(WORLD, "grey")
        newer_fingerprint = api().evidence_fingerprint(IDS)
        with newer.begin():
            assert newer_repo.reserve_reflection_attempt(WORLD, "grey", newer_fingerprint, newer_context.source_cursor)
        newer_state = newer.get(AgentCognitionState, (WORLD, "grey"))
        successful_reservation = tuple(getattr(newer_state, column.name)
            for column in AgentCognitionState.__table__.columns)
    allow_stale.set()
    older.join(5)
    assert not older.is_alive() and stale_error == []
    assert stale_result == [False]
    with Session(session.bind, expire_on_commit=False) as verify:
        final_state = verify.get(AgentCognitionState, (WORLD, "grey"))
        assert tuple(getattr(final_state, column.name)
            for column in AgentCognitionState.__table__.columns) == successful_reservation
        assert derived_counts(verify) == (0, 0, 0, 0)


def test_abandoned_reservation_consumes_quota_without_double_counting_failure(memory_session):
    session = memory_session
    repo = prepare(session)
    with session.begin():
        context = repo.reflection_context(WORLD, "grey")
    with session.begin():
        assert repo.reserve_reflection_attempt(WORLD, "grey", api().evidence_fingerprint(IDS[:3]), context.source_cursor)
    # The process could disappear here. A new Engine must see only one slot left.
    provider = DraftProvider(lambda data, request: (_ for _ in ()).throw(TimeoutError("failure")))
    assert not engine(session, provider).enrich_if_due(WORLD, "grey")
    assert not engine(session, provider).enrich_if_due(WORLD, "grey")
    assert provider.calls == 1
    state = session.get(AgentCognitionState, (WORLD, "grey"))
    assert (state.reflection_attempt_count, state.reflection_attempt_status) == (2, "failed")


def test_deadline_expired_while_reserving_does_not_start_provider(memory_session):
    session = memory_session
    prepare(session)
    now = [0.0]
    class SlowReservation(CognitionRepository):
        def reserve_reflection_attempt(self, *args):
            result = super().reserve_reflection_attempt(*args)
            now[0] = 2
            return result
    provider = DraftProvider()
    assert not engine(session, provider, SlowReservation(session)).enrich_if_due(
        WORLD, "grey", deadline=1, monotonic=lambda: now[0])
    assert provider.calls == 0
    assert derived_counts(session) == (0, 0, 0, 0)


def api():
    try:
        return importlib.import_module("backend.app.agents.reflection")
    except ModuleNotFoundError:
        pytest.fail("Reflection engine behavior is missing")


@pytest.mark.parametrize("importance,count,critical,want", [
    (1.99, 3, False, False), (2.0, 3, False, True), (3, 2, False, False), (.2, 1, True, True)])
def test_trigger_requires_threshold_and_count_unless_critical(importance, count, critical, want):
    engine = api().ReflectionEngine(None, None, None)
    assert engine.is_due(SimpleNamespace(reflection_accumulated_importance=importance,
        reflection_memory_count=count, reflection_pending_critical=critical)) is want


def test_fingerprint_is_sorted_id_sha256_and_failed_attempts_are_bounded():
    import hashlib
    ids = [str(UUID(int=2)), str(UUID(int=1))]
    fingerprint = api().evidence_fingerprint(ids)
    assert fingerprint == hashlib.sha256((str(UUID(int=1)) + "\n" + str(UUID(int=2))).encode()).hexdigest()
    assert fingerprint == api().evidence_fingerprint(list(reversed(ids)))
    engine = api().ReflectionEngine(None, None, None)
    assert engine.should_attempt(fingerprint, failed_attempts=1)
    assert not engine.should_attempt(fingerprint, failed_attempts=2)
