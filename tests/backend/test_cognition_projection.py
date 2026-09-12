"""Catch partial projections, unstable compensation and request budget overruns."""
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event as sa_event, func, select
from sqlalchemy.exc import SQLAlchemyError

from backend.app.core.config import Settings
from backend.app.database.chat_repository import ChatRepository
from backend.app.database.cognition_repository import CognitionRepository
from backend.app.database.models import AgentCognitionState, ConversationMessage, Event, Memory, Observation, WorldState
from backend.app.services.cognition_projection import CognitionProjectionError, CognitionProjectionService
from tests.backend.test_cognition_repository import source_session


@pytest.mark.parametrize("failure", [False, True])
def test_reflection_runs_after_committed_core_and_embedding_without_breaking_projection(source_session, failure):
    from backend.app.agents.reflection import ReflectionEngine
    from backend.app.agents.memory_retrieval import MemoryRetriever
    from backend.app.llm.embedding_provider import DeterministicEmbeddingProvider
    from backend.app.llm.reflection_provider import FakeReflectionProvider
    from backend.app.services.cognition_projection import EmbeddingEnrichmentService
    repo = CognitionRepository(source_session)
    repo.get_or_create_state("aleria-town", "grey").reflection_pending_critical = 1
    source_session.commit()
    observed = []
    class InspectProvider(FakeReflectionProvider):
        def reflect(self, request):
            assert not source_session.in_transaction()
            with source_session.bind.connect() as connection:
                assert connection.scalar(select(func.count()).select_from(Observation)) == 1
                statuses = connection.scalars(select(Memory.embedding_status).where(Memory.owner_npc_id == "grey")).all()
                assert statuses and set(statuses) == {"ready"}
            observed.append(True)
            if failure: raise TimeoutError("private timeout payload")
            return super().reflect(request)
    embedding = DeterministicEmbeddingProvider()
    reflection = ReflectionEngine(repo, MemoryRetriever(repo, embedding), InspectProvider())
    service = CognitionProjectionService(repo, enrichment=EmbeddingEnrichmentService(repo, embedding), reflection=reflection)
    assert service.catch_up_owner("aleria-town", "grey").created_memories == 1
    assert observed == [True] and not source_session.in_transaction()
    state = source_session.get(AgentCognitionState, ("aleria-town", "grey"))
    assert state.last_event_sequence == 3
    assert state.reflection_attempt_status == ("failed" if failure else "succeeded")
    assert source_session.get(WorldState, "aleria-town").world_version == 1


def test_shared_deadline_stops_reflection_after_embedding_consumes_budget(source_session):
    from backend.app.agents.reflection import ReflectionEngine
    from backend.app.agents.memory_retrieval import MemoryRetriever
    from backend.app.llm.embedding_provider import DeterministicEmbeddingProvider
    from backend.app.llm.reflection_provider import FakeReflectionProvider
    from backend.app.services.cognition_projection import EmbeddingEnrichmentService
    now, called = [0.0], []
    class SlowEmbedding(DeterministicEmbeddingProvider):
        def embed(self, text):
            now[0] = 6
            return super().embed(text)
    class ObserveReflection(FakeReflectionProvider):
        def reflect(self, request):
            called.append(True)
            return super().reflect(request)
    repo = CognitionRepository(source_session)
    repo.get_or_create_state("aleria-town", "grey").reflection_pending_critical = 1
    source_session.commit()
    embedding = SlowEmbedding()
    service = CognitionProjectionService(repo, monotonic=lambda: now[0],
        enrichment=EmbeddingEnrichmentService(repo, embedding),
        reflection=ReflectionEngine(repo, MemoryRetriever(repo, embedding), ObserveReflection()))
    assert service.catch_up_owner("aleria-town", "grey").created_memories == 1
    assert called == []


@pytest.mark.parametrize("surface", ["tick", "quest", "travel", "chat"])
def test_production_routes_inject_reflection_and_contain_failure(database_url, seed_dir, surface):
    from fastapi.testclient import TestClient
    from backend.app.main import create_app
    from backend.app.llm.reflection_provider import FakeReflectionProvider
    from scripts.seed_world import seed_database
    seed_database(database_url, seed_dir)
    attempted = []
    class Failure(FakeReflectionProvider):
        def reflect(self, request):
            attempted.append(request)
            raise TimeoutError("PRIVATE reflection input")
    app = create_app(database_url, settings=Settings(_env_file=None,
        reflection_importance_threshold=0, reflection_min_new_memories=1), reflection_provider=Failure())
    endpoints = {"tick": ("/api/world/tick", {"expected_world_version": 0}),
        "quest": ("/api/quests/missing-child/interact", {"interaction": "accept_quest", "expected_version": 0, "expected_world_version": 0}),
        "travel": ("/api/player/travel", {"target_location_id": "castle", "expected_world_version": 0}),
        "chat": ("/api/npcs/grey/chat", {"message": "hello"})}
    try:
        with TestClient(app) as client:
            path, body = endpoints[surface]
            response = client.post(path, json=body)
            assert response.status_code == 200, response.text
            assert attempted
            assert "PRIVATE" not in response.text
        with app.state.session_factory() as session:
            assert session.scalar(select(func.count()).select_from(Memory).where(Memory.memory_type == "reflection")) == 0
            assert session.scalar(select(func.count()).select_from(Observation)) > 0
    finally:
        app.state.session_factory.kw["bind"].dispose()


class FailingCoreRepository(CognitionRepository):
    """Fail after real core writes; verifies source hooks retain committed data."""
    def persist_core_projection(self, state, drafts):
        super().persist_core_projection(state, drafts)
        raise SQLAlchemyError("sensitive injected secret")


def count(session, model):
    return session.scalar(select(func.count()).select_from(model))


def add_turn(session, owner="grey", *, legacy=False):
    result = ChatRepository(session).persist_turn(conversation_id=str(uuid4()), create_conversation=True,
        npc_id=owner, world_id="aleria-town", clock_tick=1, turn_id=str(uuid4()), world_version=1,
        world_time="09:00", user_content="Claim: I own the castle", assistant_content="A claim received",
        emotion="neutral", provider="mock", fallback_used=False, prompt_version="v3")
    ids = (result.user.id, result.assistant.id)
    if legacy:
        for id in ids: session.get(ConversationMessage, id).world_version = None
        session.commit()
    session.rollback()
    return ids


def test_owner_projection_is_idempotent_retains_claim_time_and_accumulates_reflection(source_session):
    ids = add_turn(source_session)
    service = CognitionProjectionService(CognitionRepository(source_session))
    first = service.catch_up_owner("aleria-town", "grey")
    assert first.created_memories == first.created_observations == 2
    before_ids = tuple(source_session.scalars(select(Observation.id).order_by(Observation.id)))
    source_session.commit()  # close the test's inspection transaction before the next projection
    second = service.catch_up_owner("aleria-town", "grey")
    assert second.created_memories == 0
    assert count(source_session, Observation) == 2
    state = source_session.get(AgentCognitionState, ("aleria-town", "grey"))
    assert (state.last_event_sequence, state.last_conversation_message_id) == (3, ids[1])
    assert state.reflection_memory_count == 2
    assert state.reflection_accumulated_importance == pytest.approx(0.75)
    assert state.last_reflection_source_created_at is None and state.last_reflection_source_memory_id is None
    conversation = source_session.scalar(select(Memory).where(Memory.memory_type == "conversation"))
    assert '"speaker_kind": "player"' in conversation.content
    assert "Claim: I own the castle" in conversation.content
    assert "castle" not in conversation.safe_summary
    assert (conversation.occurred_world_version, conversation.occurred_clock_tick, conversation.occurred_world_time) == (1, 1, "09:00")
    assert conversation.embedding_status == "unavailable"
    # A lost cursor or service restart replays existing sources without extra rows or counters.
    state.last_event_sequence = state.last_conversation_message_id = 0
    source_session.commit()
    assert CognitionProjectionService(CognitionRepository(source_session)).catch_up_owner("aleria-town", "grey").created_memories == 0
    assert tuple(source_session.scalars(select(Observation.id).order_by(Observation.id))) == before_ids
    assert state.reflection_memory_count == 2
    world = source_session.get(WorldState, "aleria-town")
    assert (world.world_version, world.clock_tick, world.event_sequence) == (1, 1, 3)


def test_observation_flush_failure_rolls_back_memory_and_checkpoint_then_compensates(source_session):
    original_count = count(source_session, Memory)
    source_session.commit()
    attempted_ids = []
    def fail_after_observation_flush(session, context):
        if any(isinstance(row, Observation) for row in session.new):
            attempted_ids.extend(row.id for row in session.new if isinstance(row, Observation))
            raise SQLAlchemyError("sensitive injected secret")
    sa_event.listen(source_session, "after_flush", fail_after_observation_flush)
    service = CognitionProjectionService(CognitionRepository(source_session))
    with pytest.raises(CognitionProjectionError, match="^cognition projection unavailable$"):
        service.catch_up_owner("aleria-town", "grey")
    assert count(source_session, Observation) == 0
    assert count(source_session, Memory) == original_count
    assert source_session.get(AgentCognitionState, ("aleria-town", "grey")) is None
    sa_event.remove(source_session, "after_flush", fail_after_observation_flush)
    source_session.commit()
    assert service.catch_up_owner("aleria-town", "grey").created_memories == 1
    assert list(source_session.scalars(select(Observation.id))) == attempted_ids
    assert UUID(attempted_ids[0]).version == 5
    assert UUID(source_session.scalar(select(Memory.id).where(Memory.memory_type == "episodic"))).version == 5


def test_rollback_failure_is_still_a_safe_projection_error(source_session, monkeypatch):
    # Catches rollback/driver errors escaping the typed post-commit failure boundary.
    original_rollback = source_session.rollback
    def reported_rollback_failure():
        original_rollback()
        raise SQLAlchemyError("sensitive rollback error")
    monkeypatch.setattr(source_session, "rollback", reported_rollback_failure)
    with pytest.raises(CognitionProjectionError, match="^cognition projection unavailable$"):
        CognitionProjectionService(FailingCoreRepository(source_session)).catch_up_owner("aleria-town", "grey")


def test_world_failure_preserves_other_owner_transactions(source_session):
    def fail_ryan(session, context):
        if any(isinstance(row, Observation) and row.owner_npc_id == "ryan" for row in session.new):
            raise SQLAlchemyError("failed owner")
    sa_event.listen(source_session, "after_flush", fail_ryan)
    service = CognitionProjectionService(CognitionRepository(source_session))
    with pytest.raises(CognitionProjectionError): service.catch_up_world("aleria-town")
    assert source_session.get(AgentCognitionState, ("aleria-town", "grey")).last_event_sequence == 3
    assert source_session.get(AgentCognitionState, ("aleria-town", "ryan")) is None
    sa_event.remove(source_session, "after_flush", fail_ryan)
    source_session.commit()
    assert service.catch_up_owner("aleria-town", "ryan").created_memories == 2


def test_legacy_null_sources_advance_scanned_cursors_without_memories(source_session):
    ids = add_turn(source_session, legacy=True)
    for source in source_session.scalars(select(Event)): source.perception_scope = None
    source_session.commit()
    service = CognitionProjectionService(CognitionRepository(source_session))
    assert service.catch_up_owner("aleria-town", "grey").created_memories == 0
    state = source_session.get(AgentCognitionState, ("aleria-town", "grey"))
    assert state is not None
    assert (state.last_event_sequence, state.last_conversation_message_id) == (3, ids[1])
    assert count(source_session, Observation) == 0


def test_message_batch_is_bounded_and_does_not_split_complete_turn(source_session):
    first = add_turn(source_session)
    second = add_turn(source_session)
    third = add_turn(source_session, owner="ryan")
    service = CognitionProjectionService(CognitionRepository(source_session), settings=Settings(_env_file=None, cognition_source_batch_size=1))
    assert service.catch_up_owner("aleria-town", "grey").created_memories == 1
    state = source_session.get(AgentCognitionState, ("aleria-town", "grey"))
    assert (state.last_event_sequence, state.last_conversation_message_id) == (1, first[1])
    source_session.commit()
    assert service.catch_up_owner("aleria-town", "grey").created_memories == 1
    assert state.last_conversation_message_id == second[1] < third[1]


def test_attention_exclusion_leaves_no_hidden_observations_and_critical_accumulates(source_session):
    for source in source_session.scalars(select(Event)):
        source.participant_npc_ids_json = ["grey"]
    source_session.get(Event, 3).is_critical = 1
    source_session.commit()
    service = CognitionProjectionService(CognitionRepository(source_session), settings=Settings(_env_file=None, cognition_attention_budget=1))
    assert service.catch_up_owner("aleria-town", "grey").created_memories == 1
    assert source_session.scalar(select(Observation)).source_event_id == 3
    state = source_session.get(AgentCognitionState, ("aleria-town", "grey"))
    assert state.last_event_sequence == 3 and state.reflection_pending_critical == 1
    assert state.reflection_memory_count == 1 and state.reflection_accumulated_importance == pytest.approx(0.9)
    source_session.commit()
    assert service.catch_up_owner("aleria-town", "grey").created_memories == 0


def test_deadline_stops_before_next_owner_and_leaves_its_cursor_uncreated(source_session):
    now = [0.0]
    def advance_clock_after_commit(session): now[0] = 6.0
    sa_event.listen(source_session, "after_commit", advance_clock_after_commit)
    service = CognitionProjectionService(CognitionRepository(source_session), monotonic=lambda: now[0])
    assert service.catch_up_world("aleria-town").created_memories == 2
    assert source_session.get(AgentCognitionState, ("aleria-town", "ryan")) is not None
    assert source_session.get(AgentCognitionState, ("aleria-town", "shir")) is None
    assert source_session.get(AgentCognitionState, ("aleria-town", "grey")) is None


def test_expired_deadline_does_not_scan_or_advance_owner(source_session):
    times = iter([0.0, 6.0])
    service = CognitionProjectionService(CognitionRepository(source_session), monotonic=lambda: next(times, 6.0))
    assert service.catch_up_owner("aleria-town", "grey").created_memories == 0
    assert count(source_session, AgentCognitionState) == 0


@pytest.mark.parametrize("scope", ["owner", "world"])
@pytest.mark.parametrize("write_mode", ["pending", "flushed", "core_dml", "read_only"])
def test_projection_rejects_pending_source_writes_without_committing_them(source_session, scope, write_mode):
    # Catch commit/rollback of an existing caller transaction, including flushed writes and Core DML.
    from sqlalchemy import update
    from sqlalchemy.orm import Session
    world = source_session.get(WorldState, "aleria-town")
    if write_mode in {"pending", "flushed"}:
        world.world_version = 99
        if write_mode == "flushed": source_session.flush()
    elif write_mode == "core_dml":
        source_session.execute(update(WorldState).where(WorldState.id == "aleria-town").values(world_version=99))
    transaction = source_session.get_transaction()
    service = CognitionProjectionService(CognitionRepository(source_session))
    with pytest.raises(CognitionProjectionError):
        if scope == "owner": service.catch_up_owner("aleria-town", "grey")
        else: service.catch_up_world("aleria-town")
    assert source_session.get_transaction() is transaction and transaction.is_active
    assert world.world_version == (1 if write_mode == "read_only" else 99)
    with Session(source_session.bind) as observer:
        assert observer.get(WorldState, "aleria-town").world_version == 1
    source_session.rollback()
    assert world.world_version == 1
    assert count(source_session, Observation) == 0


def test_reused_session_refreshes_checkpoint_and_does_not_lose_other_commit_accumulators(source_session):
    # Catches stale ORM state overwriting reflection counters committed by another request.
    from sqlalchemy.orm import Session
    from backend.app.database.world_clock_repository import WorldTickRepository
    from backend.app.services.world_clock_service import WorldTickService
    service = CognitionProjectionService(CognitionRepository(source_session))
    assert service.catch_up_owner("aleria-town", "grey").created_memories == 1
    retained_state = source_session.get(AgentCognitionState, ("aleria-town", "grey"))
    source_session.rollback()
    # Load state into the identity map before another request commits.
    assert retained_state.reflection_memory_count == 1
    retained_world = source_session.get(WorldState, "aleria-town")
    assert retained_world.world_version == 1
    source_session.commit()  # keep identity-map objects, but do not lend our read transaction to cognition
    with Session(source_session.bind, expire_on_commit=False) as other:
        ticks = WorldTickService(WorldTickRepository(other))
        ticks.advance(1)
        assert CognitionProjectionService(CognitionRepository(other)).catch_up_owner("aleria-town", "grey").created_memories == 1
        ticks.advance(2)
    assert service.catch_up_owner("aleria-town", "grey").created_memories == 1
    source_session.expire_all()
    state = source_session.get(AgentCognitionState, ("aleria-town", "grey"))
    assert state.reflection_memory_count == 3
    assert state.reflection_accumulated_importance == pytest.approx(0.75)
    newest = source_session.scalar(select(Memory).where(Memory.memory_type == "episodic").order_by(Memory.occurred_clock_tick.desc()))
    assert newest.created_world_version == 3
