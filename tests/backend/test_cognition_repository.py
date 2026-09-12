"""Catch skipped backlog, duplicate writes and cross-owner/world source use."""
from dataclasses import replace

import pytest
from sqlalchemy import select

from backend.app.agents.perception import PerceptionPolicyRegistry
from backend.app.database.cognition_repository import CognitionRepository
from backend.app.database.connection import create_engine_and_session
from backend.app.database.models import AgentCognitionState, Observation, WorldState
from backend.app.services.world_clock_service import WorldTickService
from backend.app.database.world_clock_repository import WorldTickRepository
from scripts.seed_world import seed_database


@pytest.mark.parametrize("kind", ["empty", "invented", "unoffered", "owner", "world", "future", "superseded", "confidence", "length", "revision"])
def test_reflection_repository_revalidates_even_constructed_drafts(source_session, kind):
    from uuid import UUID
    from backend.app.agents.cognition_contracts import ReflectionDraft, BeliefDraft
    from backend.app.agents.reflection import evidence_fingerprint
    from backend.app.database.models import Memory
    from tests.backend.test_reflection_engine import authority, derived_counts
    from tests.backend.test_memory_retrieval import add_memory
    session = source_session
    id = str(UUID(int=701))
    add_memory(session, id, world_id="aleria-town", occurred_clock_tick=1, created_clock_tick=1)
    repository = CognitionRepository(session)
    context = repository.reflection_context("aleria-town", "grey")
    candidate_ids = {id}
    data = dict(insight="A view", confidence=.5, evidence_memory_ids=(UUID(id),),
        provider="fixture", model="fixture", prompt_version="reflection-v1", belief=None)
    if kind == "empty": data["evidence_memory_ids"] = ()
    elif kind == "invented": data["evidence_memory_ids"] = (UUID(int=999),)
    elif kind == "unoffered": candidate_ids = {str(UUID(int=998))}
    elif kind in {"owner", "world", "future", "superseded"}:
        row = session.get(Memory, id)
        field, value = {"owner": ("owner_npc_id", "ryan"), "world": ("world_id", "foreign"),
            "future": ("occurred_world_version", 2), "superseded": ("lifecycle_state", "superseded")}[kind]
        if kind == "world":
            session.add(WorldState(id="foreign", name="foreign", day=1, time="09:00", clock_tick=1, world_version=1, event_sequence=0))
            session.flush()
        setattr(row, field, value)
    elif kind == "confidence": data["confidence"] = 2
    elif kind == "length": data["insight"] = "x" * 801
    elif kind == "revision":
        data["belief"] = BeliefDraft(statement="view", safe_summary="view", confidence=.5,
            supporting_memory_ids=(UUID(id),), supersedes_belief_id=UUID(int=999), prior_belief_disposition="disputed")
    session.commit()
    before = authority(session)
    session.rollback()
    with pytest.raises(ValueError):
        with session.begin():
            repository.persist_reflection("aleria-town", "grey", ReflectionDraft.model_construct(**data),
                candidate_ids=candidate_ids, current_belief_ids=(), fingerprint=evidence_fingerprint(candidate_ids),
                source_cursor=context.source_cursor)
    assert derived_counts(session) == (0, 0, 0, 0)
    assert authority(session) == before


@pytest.fixture
def source_session(database_url, seed_dir):
    seed_database(database_url, seed_dir)
    engine, factory = create_engine_and_session(database_url)
    with factory() as session:
        WorldTickService(WorldTickRepository(session)).advance(0)
        session.rollback()  # end read-only DTO refresh transaction
        yield session
    engine.dispose()


def test_source_batch_stops_at_actual_event_limit_and_preserves_backlog(source_session):
    repository = CognitionRepository(source_session)
    state = repository.get_or_create_state("aleria-town", "grey")
    assert state is not None
    batch = repository.load_source_batch(state, event_limit=2, turn_limit=2)
    assert [e.event_sequence for e in batch.events] == [1, 2]
    assert batch.event_upper == 2
    repository.persist_core_projection(state, ())
    source_session.commit()
    assert state.last_event_sequence == 2
    assert [e.event_sequence for e in repository.load_source_batch(state, event_limit=2, turn_limit=2).events] == [3]


def test_world_lookup_never_creates_unknown_owners_or_worlds(source_session):
    repository = CognitionRepository(source_session)
    assert repository.list_npc_ids("aleria-town") == ("ryan", "shir", "grey")
    assert repository.list_npc_ids("missing") == ()
    for world, owner in (("missing", "grey"), ("aleria-town", "missing")):
        with pytest.raises(ValueError, match="cognition owner unavailable"):
            repository.get_or_create_state(world, owner)
    assert list(source_session.scalars(select(AgentCognitionState))) == []


def test_repository_refuses_foreign_owner_and_unscanned_source_drafts(source_session):
    repository = CognitionRepository(source_session)
    state = repository.get_or_create_state("aleria-town", "grey")
    assert state is not None
    batch = repository.load_source_batch(state, event_limit=3, turn_limit=2)
    drafts = PerceptionPolicyRegistry().project_batch(batch.events, batch.turns, batch.npc_profiles)
    draft = next(d for d in drafts if d.owner_npc_id == "grey")
    for invalid in (replace(draft, owner_npc_id="ryan"), replace(draft, source_key="event:999")):
        with pytest.raises(ValueError, match="cognition source unavailable"):
            repository.persist_core_projection(state, (invalid,))
    assert list(source_session.scalars(select(Observation))) == []
    assert source_session.get(WorldState, "aleria-town").event_sequence == 3
