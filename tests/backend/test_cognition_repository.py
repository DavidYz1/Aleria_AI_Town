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
