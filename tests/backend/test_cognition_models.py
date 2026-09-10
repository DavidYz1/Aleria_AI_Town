from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from backend.app.database import models
from backend.app.database.connection import create_engine_and_session
from scripts.seed_world import seed_database


COGNITION_TABLES = {
    "agent_cognition_states",
    "observations",
    "memories",
    "memory_evidence",
    "beliefs",
    "belief_evidence",
}


@pytest.fixture
def cognition_session(database_url, seed_dir):
    seed_database(database_url, seed_dir)
    engine, session_factory = create_engine_and_session(database_url)
    assert COGNITION_TABLES.issubset(inspect(engine).get_table_names())
    with session_factory() as session:
        yield session


def _observation(**overrides):
    values = {
        "id": str(uuid4()),
        "world_id": "aleria-town",
        "owner_npc_id": "grey",
        "source_kind": "authored_knowledge",
        "source_event_id": None,
        "source_turn_id": None,
        "source_user_message_id": None,
        "source_assistant_message_id": None,
        "source_key": f"event:{uuid4()}",
        "policy_version": "stage2-v1",
        "occurred_world_version": 0,
        "occurred_clock_tick": 0,
        "occurred_world_time": "08:00",
        "source_created_at": datetime.now(UTC),
        "created_at": datetime.now(UTC),
        "perception_mode": "witnessed",
        "facts_json": {},
        "related_entity_ids_json": [],
        "summary": "Observed event",
        "secrecy": "public",
        "disclosure_scope": "public",
        "lifecycle_state": "active",
        "is_critical": 0,
    }
    values.update(overrides)
    return models.Observation(**values)


def _knowledge_memory(**overrides):
    values = {
        "id": str(uuid4()),
        "world_id": "aleria-town",
        "owner_npc_id": "grey",
        "memory_type": "knowledge",
        "source_observation_id": None,
        "authored_source_id": f"source-{uuid4()}",
        "authored_source_version": "stage2-v1",
        "content": "Stable authored knowledge",
        "safe_summary": "Safe stable knowledge",
        "normalized_content_hash": "a" * 64,
        "related_entity_ids_json": [],
        "occurred_world_version": 0,
        "occurred_clock_tick": 0,
        "created_world_version": 0,
        "created_clock_tick": 0,
        "occurred_world_time": "08:00",
        "source_created_at": datetime.now(UTC),
        "created_at": datetime.now(UTC),
        "importance": 0.5,
        "confidence": 0.5,
        "emotional_valence": 0.0,
        "secrecy": "private",
        "disclosure_scope": "player_dialogue",
        "lifecycle_state": "active",
        "embedding_provider": None,
        "embedding_model": None,
        "embedding_version": None,
        "embedding_input_hash": None,
        "embedding_dimensions": None,
        "embedding_status": "unavailable",
        "embedding": None,
        "last_accessed_at": None,
        "access_count": 0,
    }
    values.update(overrides)
    return models.Memory(**values)


def test_cognition_orm_uses_stable_primary_key_constraint_names():
    assert {
        table_name: models.Base.metadata.tables[table_name].primary_key.name
        for table_name in COGNITION_TABLES
    } == {
        "agent_cognition_states": "pk_agent_cognition_states",
        "observations": "pk_observations",
        "memories": "pk_memories",
        "memory_evidence": "pk_memory_evidence",
        "beliefs": "pk_beliefs",
        "belief_evidence": "pk_belief_evidence",
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [("importance", 1.1), ("confidence", -0.1), ("emotional_valence", 1.1)],
)
def test_memory_rejects_out_of_range_scores(cognition_session, field, value):
    cognition_session.add(_knowledge_memory(**{field: value}))
    with pytest.raises(IntegrityError):
        cognition_session.commit()


def test_observation_owner_source_policy_is_unique(cognition_session):
    source_key = "event:shared"
    cognition_session.add_all([
        _observation(source_key=source_key),
        _observation(source_key=source_key),
    ])
    with pytest.raises(IntegrityError):
        cognition_session.commit()


@pytest.mark.parametrize(
    "values",
    [
        {"memory_type": "episodic", "source_observation_id": None,
         "authored_source_id": None, "authored_source_version": None},
        {"memory_type": "knowledge", "source_observation_id": None,
         "authored_source_id": None, "authored_source_version": None},
        {"memory_type": "reflection", "source_observation_id": "observation",
         "authored_source_id": None, "authored_source_version": None},
    ],
)
def test_memory_rejects_invalid_direct_source_shape(cognition_session, values):
    cognition_session.add(_knowledge_memory(**values))
    with pytest.raises(IntegrityError):
        cognition_session.commit()


def test_memory_evidence_ordinal_is_unique_per_derived_memory(cognition_session):
    derived = _knowledge_memory(memory_type="reflection", authored_source_id=None,
                                authored_source_version=None)
    evidence_a = _knowledge_memory()
    evidence_b = _knowledge_memory()
    cognition_session.add_all([derived, evidence_a, evidence_b])
    cognition_session.flush()
    cognition_session.add_all([
        models.MemoryEvidence(derived_memory_id=derived.id,
                              evidence_memory_id=evidence_a.id, ordinal=0),
        models.MemoryEvidence(derived_memory_id=derived.id,
                              evidence_memory_id=evidence_b.id, ordinal=0),
    ])
    with pytest.raises(IntegrityError):
        cognition_session.commit()


@pytest.mark.parametrize(
    "record",
    [
        lambda: _observation(world_id="missing-world"),
        lambda: _knowledge_memory(owner_npc_id="missing-npc"),
        lambda: models.MemoryEvidence(
            derived_memory_id=str(uuid4()),
            evidence_memory_id=str(uuid4()),
            ordinal=0,
        ),
    ],
)
def test_cognition_models_reject_dangling_foreign_keys(cognition_session, record):
    cognition_session.add(record())
    with pytest.raises(IntegrityError):
        cognition_session.commit()
