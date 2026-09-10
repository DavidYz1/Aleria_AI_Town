from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
)
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, synonym


class Base(DeclarativeBase):
    pass


class WorldState(Base):
    __tablename__ = "world_state"
    __table_args__ = (
        CheckConstraint("day >= 1"),
        CheckConstraint("clock_tick >= 0"),
        CheckConstraint("world_version >= 0"),
        CheckConstraint("event_sequence >= 0"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    day: Mapped[int] = mapped_column(Integer, nullable=False)
    time: Mapped[str] = mapped_column(String(5), nullable=False)
    clock_tick: Mapped[int] = mapped_column(Integer, nullable=False)
    world_version: Mapped[int] = mapped_column(Integer, nullable=False)
    event_sequence: Mapped[int] = mapped_column(Integer, nullable=False)


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)


class NpcProfile(Base):
    __tablename__ = "npc_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    personality_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)


class NpcState(Base):
    __tablename__ = "npc_states"
    __table_args__ = (
        CheckConstraint("energy BETWEEN 0 AND 100"),
        CheckConstraint("mood BETWEEN 0 AND 100"),
        CheckConstraint("social BETWEEN 0 AND 100"),
    )

    npc_id: Mapped[str] = mapped_column(
        ForeignKey("npc_profiles.id"), primary_key=True
    )
    location_id: Mapped[str] = mapped_column(
        ForeignKey("locations.id"), nullable=False
    )
    current_action: Mapped[str] = mapped_column(String, nullable=False)
    energy: Mapped[int] = mapped_column(Integer, nullable=False)
    mood: Mapped[int] = mapped_column(Integer, nullable=False)
    social: Mapped[int] = mapped_column(Integer, nullable=False)


class PlayerState(Base):
    __tablename__ = "player_states"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    world_id: Mapped[str] = mapped_column(
        ForeignKey("world_state.id"), nullable=False
    )
    location_id: Mapped[str] = mapped_column(
        ForeignKey("locations.id"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class QuestProgress(Base):
    __tablename__ = "quest_progress"
    __table_args__ = (
        CheckConstraint("version >= 0"),
        CheckConstraint("updated_clock_tick >= 0"),
    )

    player_id: Mapped[str] = mapped_column(
        ForeignKey("player_states.id"), primary_key=True
    )
    quest_id: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_clock_tick: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class QuestEvent(Base):
    __tablename__ = "quest_events"
    __table_args__ = (
        CheckConstraint("clock_tick >= 0"),
        Index(
            "ix_quest_events_player_quest_id",
            "player_id",
            "quest_id",
            "id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[str] = mapped_column(
        ForeignKey("player_states.id"), nullable=False
    )
    quest_id: Mapped[str] = mapped_column(String, nullable=False)
    from_status: Mapped[str] = mapped_column(String, nullable=False)
    to_status: Mapped[str] = mapped_column(String, nullable=False)
    interaction: Mapped[str] = mapped_column(String, nullable=False)
    location_id: Mapped[str] = mapped_column(
        ForeignKey("locations.id"), nullable=False
    )
    clock_tick: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    world_id: Mapped[str] = mapped_column(ForeignKey("world_state.id"), index=True)
    mode: Mapped[str] = mapped_column(String)
    trigger_type: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    base_world_version: Mapped[int] = mapped_column(Integer)
    resulting_world_version: Mapped[int] = mapped_column(Integer)
    base_clock_tick: Mapped[int] = mapped_column(Integer)
    resulting_clock_tick: Mapped[int] = mapped_column(Integer)
    correlation_id: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)


class ActionProposalRecord(Base):
    __tablename__ = "action_proposals"
    __table_args__ = (UniqueConstraint("run_id", "ordinal"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id"))
    ordinal: Mapped[int] = mapped_column(Integer)
    actor_id: Mapped[str] = mapped_column(String)
    action_type: Mapped[str] = mapped_column(String)
    target_kind: Mapped[str | None] = mapped_column(String, nullable=True)
    target_id: Mapped[str | None] = mapped_column(String, nullable=True)
    reason_code: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String)
    payload_json: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String)
    rejection_code: Mapped[str | None] = mapped_column(String, nullable=True)
    rejection_message: Mapped[str | None] = mapped_column(String, nullable=True)


class AgentTraceEntry(Base):
    __tablename__ = "agent_trace_entries"
    __table_args__ = (UniqueConstraint("run_id", "sequence"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id"))
    sequence: Mapped[int] = mapped_column(Integer)
    stage: Mapped[str] = mapped_column(String)
    actor_id: Mapped[str | None] = mapped_column(String, nullable=True)
    summary: Mapped[str] = mapped_column(String)
    data_json: Mapped[dict] = mapped_column(JSON)
    visibility: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WorldAction(Base):
    __tablename__ = "actions"
    __table_args__ = (
        CheckConstraint("clock_tick >= 1"),
        UniqueConstraint("world_id", "clock_tick", "actor_id"),
        Index("ix_actions_actor_clock_tick", "actor_id", "clock_tick"),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    world_id: Mapped[str] = mapped_column(
        ForeignKey("world_state.id"), nullable=False
    )
    clock_tick: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_id: Mapped[str] = mapped_column(
        ForeignKey("npc_profiles.id"), nullable=False
    )
    action_type: Mapped[str] = mapped_column(String, nullable=False)
    target_kind: Mapped[str | None] = mapped_column(String, nullable=True)
    target_id: Mapped[str | None] = mapped_column(String, nullable=True)
    reason_code: Mapped[str] = mapped_column(String, nullable=False)
    reason = synonym("reason_code")
    run_id: Mapped[str | None] = mapped_column(ForeignKey("agent_runs.id"), nullable=True)
    proposal_id: Mapped[int | None] = mapped_column(ForeignKey("action_proposals.id"), nullable=True)
    world_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    status: Mapped[str] = mapped_column(String, nullable=False, default="executed")
    world_time: Mapped[str] = mapped_column(String(5), nullable=False)


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("clock_tick >= 0"),
        CheckConstraint(
            "perception_scope IS NULL OR perception_scope IN "
            "('world_public', 'location', 'participants', 'professional', 'private')",
            name="ck_events_perception_scope",
        ),
        CheckConstraint(
            "attention_priority IS NULL OR attention_priority BETWEEN 0 AND 1",
            name="ck_events_attention_priority",
        ),
        CheckConstraint(
            "is_critical IS NULL OR is_critical IN (0, 1)",
            name="ck_events_is_critical",
        ),
        UniqueConstraint("world_id", "event_sequence"),
        Index("ix_events_actor_clock_tick", "actor_id", "clock_tick"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    world_id: Mapped[str] = mapped_column(
        ForeignKey("world_state.id"), nullable=False
    )
    clock_tick: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    actor_id: Mapped[str | None] = mapped_column(
        ForeignKey("npc_profiles.id"), nullable=True
    )
    action_id: Mapped[int | None] = mapped_column(
        ForeignKey("actions.id"), nullable=True, unique=True
    )
    description: Mapped[str] = mapped_column(String, nullable=False)
    world_time: Mapped[str] = mapped_column(String(5), nullable=False)

    run_id: Mapped[str | None] = mapped_column(ForeignKey("agent_runs.id"), nullable=True)
    world_version: Mapped[int] = mapped_column(Integer)
    event_sequence: Mapped[int] = mapped_column(Integer)
    source_event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id"), nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSON)
    visibility: Mapped[str] = mapped_column(String, default="public")
    secrecy: Mapped[str] = mapped_column(String, default="public")
    causation_id: Mapped[str | None] = mapped_column(String, nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    location_id: Mapped[str | None] = mapped_column(
        ForeignKey("locations.id", name="fk_events_location_id_locations"), nullable=True
    )
    perception_scope: Mapped[str | None] = mapped_column(String, nullable=True)
    participant_npc_ids_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    witness_npc_ids_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    professional_channels_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    attention_priority: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_critical: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint("created_clock_tick >= 0"),
        Index("ix_conversations_npc_updated", "npc_id", "updated_at"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    world_id: Mapped[str] = mapped_column(
        ForeignKey("world_state.id"), nullable=False
    )
    npc_id: Mapped[str] = mapped_column(
        ForeignKey("npc_profiles.id"), nullable=False
    )
    created_clock_tick: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')"),
        CheckConstraint("fallback_used IN (0, 1)"),
        CheckConstraint("clock_tick >= 0"),
        CheckConstraint(
            "world_version IS NULL OR world_version >= 0",
            name="ck_conversation_messages_world_version",
        ),
        UniqueConstraint(
            "conversation_id",
            "turn_id",
            "role",
            name="uq_conversation_messages_conversation_turn_role",
        ),
        Index(
            "ix_conversation_messages_conversation_id_id",
            "conversation_id",
            "id",
        ),
        Index("ix_conversation_messages_turn_id_id", "turn_id", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(String, nullable=False)
    emotion: Mapped[str | None] = mapped_column(String, nullable=True)
    provider: Mapped[str | None] = mapped_column(String, nullable=True)
    fallback_used: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    prompt_version: Mapped[str | None] = mapped_column(String, nullable=True)
    clock_tick: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    turn_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    world_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    world_time: Mapped[str | None] = mapped_column(String(5), nullable=True)


class AgentCognitionState(Base):
    __tablename__ = "agent_cognition_states"
    __table_args__ = (
        PrimaryKeyConstraint("world_id", "owner_npc_id", name="pk_agent_cognition_states"),
        CheckConstraint("last_event_sequence >= 0", name="ck_cognition_states_event_cursor"),
        CheckConstraint("last_conversation_message_id >= 0", name="ck_cognition_states_message_cursor"),
        CheckConstraint("reflection_accumulated_importance >= 0", name="ck_cognition_states_reflection_importance"),
        CheckConstraint("reflection_memory_count >= 0", name="ck_cognition_states_reflection_count"),
        CheckConstraint("reflection_pending_critical IN (0, 1)", name="ck_cognition_states_pending_critical"),
        CheckConstraint("reflection_attempt_count BETWEEN 0 AND 2", name="ck_cognition_states_attempt_count"),
        CheckConstraint("reflection_attempt_status IN ('idle', 'failed', 'succeeded')", name="ck_cognition_states_attempt_status"),
    )

    world_id: Mapped[str] = mapped_column(ForeignKey("world_state.id", name="fk_cognition_states_world_id_world_state"), primary_key=True)
    owner_npc_id: Mapped[str] = mapped_column(ForeignKey("npc_profiles.id", name="fk_cognition_states_owner_npc_id_npc_profiles"), primary_key=True)
    last_event_sequence: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_conversation_message_id: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    reflection_accumulated_importance: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    reflection_memory_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    reflection_pending_critical: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_reflection_source_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reflection_source_memory_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    last_reflection_evidence_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reflection_attempt_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reflection_attempt_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    reflection_attempt_status: Mapped[str] = mapped_column(String, default="idle", server_default="idle")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class Observation(Base):
    __tablename__ = "observations"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_observations"),
        UniqueConstraint("world_id", "owner_npc_id", "source_key", "policy_version", name="uq_observations_owner_source_policy"),
        CheckConstraint("source_kind IN ('event', 'conversation_turn', 'authored_knowledge')", name="ck_observations_source_kind"),
        CheckConstraint(
            "(source_kind = 'event' AND source_event_id IS NOT NULL AND source_turn_id IS NULL "
            "AND source_user_message_id IS NULL AND source_assistant_message_id IS NULL) OR "
            "(source_kind = 'conversation_turn' AND source_event_id IS NULL AND source_turn_id IS NOT NULL "
            "AND source_user_message_id IS NOT NULL AND source_assistant_message_id IS NOT NULL) OR "
            "(source_kind = 'authored_knowledge' AND source_event_id IS NULL AND source_turn_id IS NULL "
            "AND source_user_message_id IS NULL AND source_assistant_message_id IS NULL)",
            name="ck_observations_source_reference_shape",
        ),
        CheckConstraint("occurred_world_version >= 0", name="ck_observations_world_version"),
        CheckConstraint("occurred_clock_tick >= 0", name="ck_observations_clock_tick"),
        CheckConstraint("perception_mode IN ('participant', 'witnessed', 'professional_channel', 'direct_dialogue')", name="ck_observations_perception_mode"),
        CheckConstraint("secrecy IN ('public', 'private', 'secret')", name="ck_observations_secrecy"),
        CheckConstraint("disclosure_scope IN ('public', 'player_dialogue', 'internal_only')", name="ck_observations_disclosure_scope"),
        CheckConstraint("lifecycle_state IN ('active', 'archived', 'disputed', 'superseded')", name="ck_observations_lifecycle_state"),
        CheckConstraint("is_critical IN (0, 1)", name="ck_observations_is_critical"),
        Index("ix_observations_owner_occurred", "world_id", "owner_npc_id", "occurred_clock_tick", "id"),
        Index("ix_observations_source_event", "source_event_id"),
        Index("ix_observations_source_turn", "source_turn_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    world_id: Mapped[str] = mapped_column(ForeignKey("world_state.id", name="fk_observations_world_id_world_state"))
    owner_npc_id: Mapped[str] = mapped_column(ForeignKey("npc_profiles.id", name="fk_observations_owner_npc_id_npc_profiles"))
    source_kind: Mapped[str] = mapped_column(String)
    source_event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id", name="fk_observations_source_event_id_events"), nullable=True)
    source_turn_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_user_message_id: Mapped[int | None] = mapped_column(ForeignKey("conversation_messages.id", name="fk_observations_source_user_message_id_messages"), nullable=True)
    source_assistant_message_id: Mapped[int | None] = mapped_column(ForeignKey("conversation_messages.id", name="fk_observations_source_assistant_message_id_messages"), nullable=True)
    source_key: Mapped[str] = mapped_column(String)
    policy_version: Mapped[str] = mapped_column(String)
    occurred_world_version: Mapped[int] = mapped_column(Integer)
    occurred_clock_tick: Mapped[int] = mapped_column(Integer)
    occurred_world_time: Mapped[str] = mapped_column(String(5))
    source_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    perception_mode: Mapped[str] = mapped_column(String)
    facts_json: Mapped[dict] = mapped_column(JSON)
    related_entity_ids_json: Mapped[list[str]] = mapped_column(JSON)
    summary: Mapped[str] = mapped_column(Text)
    secrecy: Mapped[str] = mapped_column(String)
    disclosure_scope: Mapped[str] = mapped_column(String)
    lifecycle_state: Mapped[str] = mapped_column(String)
    is_critical: Mapped[int] = mapped_column(Integer)


class Memory(Base):
    __tablename__ = "memories"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_memories"),
        UniqueConstraint("source_observation_id", name="uq_memories_source_observation"),
        UniqueConstraint("world_id", "owner_npc_id", "authored_source_id", "authored_source_version", name="uq_memories_authored_source"),
        CheckConstraint(
            "(memory_type IN ('episodic', 'conversation') AND source_observation_id IS NOT NULL "
            "AND authored_source_id IS NULL AND authored_source_version IS NULL) OR "
            "(memory_type = 'knowledge' AND source_observation_id IS NULL AND authored_source_id IS NOT NULL "
            "AND authored_source_version IS NOT NULL) OR "
            "(memory_type = 'reflection' AND source_observation_id IS NULL AND authored_source_id IS NULL "
            "AND authored_source_version IS NULL)", name="ck_memories_source_reference_shape"),
        CheckConstraint("memory_type IN ('episodic', 'conversation', 'reflection', 'knowledge')", name="ck_memories_memory_type"),
        CheckConstraint("occurred_world_version >= 0", name="ck_memories_occurred_world_version"),
        CheckConstraint("occurred_clock_tick >= 0", name="ck_memories_occurred_clock_tick"),
        CheckConstraint("created_world_version >= 0", name="ck_memories_created_world_version"),
        CheckConstraint("created_clock_tick >= 0", name="ck_memories_created_clock_tick"),
        CheckConstraint("importance BETWEEN 0 AND 1", name="ck_memories_importance"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_memories_confidence"),
        CheckConstraint("emotional_valence BETWEEN -1 AND 1", name="ck_memories_emotional_valence"),
        CheckConstraint("secrecy IN ('public', 'private', 'secret')", name="ck_memories_secrecy"),
        CheckConstraint("disclosure_scope IN ('public', 'player_dialogue', 'internal_only')", name="ck_memories_disclosure_scope"),
        CheckConstraint("lifecycle_state IN ('active', 'archived', 'disputed', 'superseded')", name="ck_memories_lifecycle_state"),
        CheckConstraint("embedding_dimensions IS NULL OR embedding_dimensions > 0", name="ck_memories_embedding_dimensions"),
        CheckConstraint("embedding_status IN ('ready', 'failed', 'unavailable')", name="ck_memories_embedding_status"),
        CheckConstraint("access_count >= 0", name="ck_memories_access_count"),
        Index("ix_memories_owner_lifecycle_occurred", "world_id", "owner_npc_id", "lifecycle_state", "occurred_clock_tick", "id"),
        Index("ix_memories_embedding_space", "embedding_provider", "embedding_model", "embedding_version", "embedding_dimensions"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    world_id: Mapped[str] = mapped_column(ForeignKey("world_state.id", name="fk_memories_world_id_world_state"))
    owner_npc_id: Mapped[str] = mapped_column(ForeignKey("npc_profiles.id", name="fk_memories_owner_npc_id_npc_profiles"))
    memory_type: Mapped[str] = mapped_column(String)
    source_observation_id: Mapped[str | None] = mapped_column(ForeignKey("observations.id", name="fk_memories_source_observation_id_observations"), nullable=True)
    authored_source_id: Mapped[str | None] = mapped_column(String, nullable=True)
    authored_source_version: Mapped[str | None] = mapped_column(String, nullable=True)
    content: Mapped[str] = mapped_column(Text)
    safe_summary: Mapped[str] = mapped_column(Text)
    normalized_content_hash: Mapped[str] = mapped_column(String(64))
    related_entity_ids_json: Mapped[list[str]] = mapped_column(JSON)
    occurred_world_version: Mapped[int] = mapped_column(Integer)
    occurred_clock_tick: Mapped[int] = mapped_column(Integer)
    created_world_version: Mapped[int] = mapped_column(Integer)
    created_clock_tick: Mapped[int] = mapped_column(Integer)
    occurred_world_time: Mapped[str] = mapped_column(String(5))
    source_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    importance: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    emotional_valence: Mapped[float] = mapped_column(Float)
    secrecy: Mapped[str] = mapped_column(String)
    disclosure_scope: Mapped[str] = mapped_column(String)
    lifecycle_state: Mapped[str] = mapped_column(String)
    embedding_provider: Mapped[str | None] = mapped_column(String, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String, nullable=True)
    embedding_version: Mapped[str | None] = mapped_column(String, nullable=True)
    embedding_input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    embedding_dimensions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding_status: Mapped[str] = mapped_column(String)
    embedding: Mapped[list[float] | None] = mapped_column(JSON().with_variant(Vector(), "postgresql"), nullable=True)
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    access_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class MemoryEvidence(Base):
    __tablename__ = "memory_evidence"
    __table_args__ = (
        PrimaryKeyConstraint("derived_memory_id", "evidence_memory_id", name="pk_memory_evidence"),
        UniqueConstraint("derived_memory_id", "ordinal", name="uq_memory_evidence_derived_ordinal"),
        CheckConstraint("ordinal >= 0", name="ck_memory_evidence_ordinal"),
        CheckConstraint("derived_memory_id <> evidence_memory_id", name="ck_memory_evidence_no_self_reference"),
    )

    derived_memory_id: Mapped[str] = mapped_column(ForeignKey("memories.id", name="fk_memory_evidence_derived_memory_id_memories"), primary_key=True)
    evidence_memory_id: Mapped[str] = mapped_column(ForeignKey("memories.id", name="fk_memory_evidence_evidence_memory_id_memories"), primary_key=True)
    ordinal: Mapped[int] = mapped_column(Integer)


class Belief(Base):
    __tablename__ = "beliefs"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_beliefs"),
        UniqueConstraint("source_reflection_memory_id", name="uq_beliefs_source_reflection_memory"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_beliefs_confidence"),
        CheckConstraint("lifecycle_state IN ('active', 'disputed', 'superseded')", name="ck_beliefs_lifecycle_state"),
        CheckConstraint("created_world_version >= 0", name="ck_beliefs_created_world_version"),
        CheckConstraint("created_clock_tick >= 0", name="ck_beliefs_created_clock_tick"),
        Index("ix_beliefs_owner_lifecycle_created", "world_id", "owner_npc_id", "lifecycle_state", "created_clock_tick", "id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    world_id: Mapped[str] = mapped_column(ForeignKey("world_state.id", name="fk_beliefs_world_id_world_state"))
    owner_npc_id: Mapped[str] = mapped_column(ForeignKey("npc_profiles.id", name="fk_beliefs_owner_npc_id_npc_profiles"))
    statement: Mapped[str] = mapped_column(Text)
    safe_summary: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    lifecycle_state: Mapped[str] = mapped_column(String)
    supersedes_belief_id: Mapped[str | None] = mapped_column(ForeignKey("beliefs.id", name="fk_beliefs_supersedes_belief_id_beliefs"), nullable=True)
    source_reflection_memory_id: Mapped[str] = mapped_column(ForeignKey("memories.id", name="fk_beliefs_source_reflection_memory_id_memories"))
    created_world_version: Mapped[int] = mapped_column(Integer)
    created_clock_tick: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class BeliefEvidence(Base):
    __tablename__ = "belief_evidence"
    __table_args__ = (
        PrimaryKeyConstraint("belief_id", "memory_id", "evidence_role", name="pk_belief_evidence"),
        UniqueConstraint("belief_id", "evidence_role", "ordinal", name="uq_belief_evidence_role_ordinal"),
        CheckConstraint("evidence_role IN ('supporting', 'contradicting')", name="ck_belief_evidence_role"),
        CheckConstraint("ordinal >= 0", name="ck_belief_evidence_ordinal"),
    )

    belief_id: Mapped[str] = mapped_column(ForeignKey("beliefs.id", name="fk_belief_evidence_belief_id_beliefs"), primary_key=True)
    memory_id: Mapped[str] = mapped_column(ForeignKey("memories.id", name="fk_belief_evidence_memory_id_memories"), primary_key=True)
    evidence_role: Mapped[str] = mapped_column(String, primary_key=True)
    ordinal: Mapped[int] = mapped_column(Integer)
