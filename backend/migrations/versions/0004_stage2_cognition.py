"""Add Stage 2 cognition storage and immutable source metadata."""

from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    with op.batch_alter_table("events") as batch:
        batch.add_column(sa.Column("location_id", sa.String(), nullable=True))
        batch.add_column(sa.Column("perception_scope", sa.String(), nullable=True))
        batch.add_column(sa.Column("participant_npc_ids_json", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("witness_npc_ids_json", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("professional_channels_json", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("attention_priority", sa.Float(), nullable=True))
        batch.add_column(sa.Column("is_critical", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_events_location_id_locations", "locations", ["location_id"], ["id"]
        )
        batch.create_check_constraint(
            "ck_events_perception_scope",
            "perception_scope IS NULL OR perception_scope IN "
            "('world_public', 'location', 'participants', 'professional', 'private')",
        )
        batch.create_check_constraint(
            "ck_events_attention_priority",
            "attention_priority IS NULL OR attention_priority BETWEEN 0 AND 1",
        )
        batch.create_check_constraint(
            "ck_events_is_critical", "is_critical IS NULL OR is_critical IN (0, 1)"
        )

    with op.batch_alter_table("conversation_messages") as batch:
        batch.add_column(sa.Column("turn_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("world_version", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("world_time", sa.String(5), nullable=True))
        batch.create_check_constraint(
            "ck_conversation_messages_world_version",
            "world_version IS NULL OR world_version >= 0",
        )
        batch.create_unique_constraint(
            "uq_conversation_messages_conversation_turn_role",
            ["conversation_id", "turn_id", "role"],
        )
        batch.create_index(
            "ix_conversation_messages_turn_id_id", ["turn_id", "id"]
        )

    op.create_table(
        "agent_cognition_states",
        sa.Column("world_id", sa.String(), nullable=False),
        sa.Column("owner_npc_id", sa.String(), nullable=False),
        sa.Column("last_event_sequence", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_conversation_message_id", sa.Integer(), server_default="0", nullable=False),
        sa.Column("reflection_accumulated_importance", sa.Float(), server_default="0", nullable=False),
        sa.Column("reflection_memory_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("reflection_pending_critical", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_reflection_source_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_reflection_source_memory_id", sa.String(36), nullable=True),
        sa.Column("last_reflection_evidence_fingerprint", sa.String(64), nullable=True),
        sa.Column("reflection_attempt_fingerprint", sa.String(64), nullable=True),
        sa.Column("reflection_attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("reflection_attempt_status", sa.String(), server_default="idle", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("world_id", "owner_npc_id", name="pk_agent_cognition_states"),
        sa.ForeignKeyConstraint(["world_id"], ["world_state.id"], name="fk_cognition_states_world_id_world_state"),
        sa.ForeignKeyConstraint(["owner_npc_id"], ["npc_profiles.id"], name="fk_cognition_states_owner_npc_id_npc_profiles"),
        sa.CheckConstraint("last_event_sequence >= 0", name="ck_cognition_states_event_cursor"),
        sa.CheckConstraint("last_conversation_message_id >= 0", name="ck_cognition_states_message_cursor"),
        sa.CheckConstraint("reflection_accumulated_importance >= 0", name="ck_cognition_states_reflection_importance"),
        sa.CheckConstraint("reflection_memory_count >= 0", name="ck_cognition_states_reflection_count"),
        sa.CheckConstraint("reflection_pending_critical IN (0, 1)", name="ck_cognition_states_pending_critical"),
        sa.CheckConstraint("reflection_attempt_count BETWEEN 0 AND 2", name="ck_cognition_states_attempt_count"),
        sa.CheckConstraint("reflection_attempt_status IN ('idle', 'failed', 'succeeded')", name="ck_cognition_states_attempt_status"),
    )

    op.create_table(
        "observations",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("world_id", sa.String(), nullable=False),
        sa.Column("owner_npc_id", sa.String(), nullable=False),
        sa.Column("source_kind", sa.String(), nullable=False),
        sa.Column("source_event_id", sa.Integer(), nullable=True),
        sa.Column("source_turn_id", sa.String(36), nullable=True),
        sa.Column("source_user_message_id", sa.Integer(), nullable=True),
        sa.Column("source_assistant_message_id", sa.Integer(), nullable=True),
        sa.Column("source_key", sa.String(), nullable=False),
        sa.Column("policy_version", sa.String(), nullable=False),
        sa.Column("occurred_world_version", sa.Integer(), nullable=False),
        sa.Column("occurred_clock_tick", sa.Integer(), nullable=False),
        sa.Column("occurred_world_time", sa.String(5), nullable=False),
        sa.Column("source_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("perception_mode", sa.String(), nullable=False),
        sa.Column("facts_json", sa.JSON(), nullable=False),
        sa.Column("related_entity_ids_json", sa.JSON(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("secrecy", sa.String(), nullable=False),
        sa.Column("disclosure_scope", sa.String(), nullable=False),
        sa.Column("lifecycle_state", sa.String(), nullable=False),
        sa.Column("is_critical", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_observations"),
        sa.ForeignKeyConstraint(["world_id"], ["world_state.id"], name="fk_observations_world_id_world_state"),
        sa.ForeignKeyConstraint(["owner_npc_id"], ["npc_profiles.id"], name="fk_observations_owner_npc_id_npc_profiles"),
        sa.ForeignKeyConstraint(["source_event_id"], ["events.id"], name="fk_observations_source_event_id_events"),
        sa.ForeignKeyConstraint(["source_user_message_id"], ["conversation_messages.id"], name="fk_observations_source_user_message_id_messages"),
        sa.ForeignKeyConstraint(["source_assistant_message_id"], ["conversation_messages.id"], name="fk_observations_source_assistant_message_id_messages"),
        sa.UniqueConstraint("world_id", "owner_npc_id", "source_key", "policy_version", name="uq_observations_owner_source_policy"),
        sa.CheckConstraint("source_kind IN ('event', 'conversation_turn', 'authored_knowledge')", name="ck_observations_source_kind"),
        sa.CheckConstraint(
            "(source_kind = 'event' AND source_event_id IS NOT NULL AND source_turn_id IS NULL "
            "AND source_user_message_id IS NULL AND source_assistant_message_id IS NULL) OR "
            "(source_kind = 'conversation_turn' AND source_event_id IS NULL AND source_turn_id IS NOT NULL "
            "AND source_user_message_id IS NOT NULL AND source_assistant_message_id IS NOT NULL) OR "
            "(source_kind = 'authored_knowledge' AND source_event_id IS NULL AND source_turn_id IS NULL "
            "AND source_user_message_id IS NULL AND source_assistant_message_id IS NULL)",
            name="ck_observations_source_reference_shape",
        ),
        sa.CheckConstraint("occurred_world_version >= 0", name="ck_observations_world_version"),
        sa.CheckConstraint("occurred_clock_tick >= 0", name="ck_observations_clock_tick"),
        sa.CheckConstraint("perception_mode IN ('participant', 'witnessed', 'professional_channel', 'direct_dialogue')", name="ck_observations_perception_mode"),
        sa.CheckConstraint("secrecy IN ('public', 'private', 'secret')", name="ck_observations_secrecy"),
        sa.CheckConstraint("disclosure_scope IN ('public', 'player_dialogue', 'internal_only')", name="ck_observations_disclosure_scope"),
        sa.CheckConstraint("lifecycle_state IN ('active', 'archived', 'disputed', 'superseded')", name="ck_observations_lifecycle_state"),
        sa.CheckConstraint("is_critical IN (0, 1)", name="ck_observations_is_critical"),
    )
    op.create_index("ix_observations_owner_occurred", "observations", ["world_id", "owner_npc_id", "occurred_clock_tick", "id"])
    op.create_index("ix_observations_source_event", "observations", ["source_event_id"])
    op.create_index("ix_observations_source_turn", "observations", ["source_turn_id"])

    embedding_type = Vector() if bind.dialect.name == "postgresql" else sa.JSON()
    op.create_table(
        "memories",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("world_id", sa.String(), nullable=False),
        sa.Column("owner_npc_id", sa.String(), nullable=False),
        sa.Column("memory_type", sa.String(), nullable=False),
        sa.Column("source_observation_id", sa.String(36), nullable=True),
        sa.Column("authored_source_id", sa.String(), nullable=True),
        sa.Column("authored_source_version", sa.String(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("safe_summary", sa.Text(), nullable=False),
        sa.Column("normalized_content_hash", sa.String(64), nullable=False),
        sa.Column("related_entity_ids_json", sa.JSON(), nullable=False),
        sa.Column("occurred_world_version", sa.Integer(), nullable=False),
        sa.Column("occurred_clock_tick", sa.Integer(), nullable=False),
        sa.Column("created_world_version", sa.Integer(), nullable=False),
        sa.Column("created_clock_tick", sa.Integer(), nullable=False),
        sa.Column("occurred_world_time", sa.String(5), nullable=False),
        sa.Column("source_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("importance", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("emotional_valence", sa.Float(), nullable=False),
        sa.Column("secrecy", sa.String(), nullable=False),
        sa.Column("disclosure_scope", sa.String(), nullable=False),
        sa.Column("lifecycle_state", sa.String(), nullable=False),
        sa.Column("embedding_provider", sa.String(), nullable=True),
        sa.Column("embedding_model", sa.String(), nullable=True),
        sa.Column("embedding_version", sa.String(), nullable=True),
        sa.Column("embedding_input_hash", sa.String(64), nullable=True),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=True),
        sa.Column("embedding_status", sa.String(), nullable=False),
        sa.Column("embedding", embedding_type, nullable=True),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("access_count", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_memories"),
        sa.ForeignKeyConstraint(["world_id"], ["world_state.id"], name="fk_memories_world_id_world_state"),
        sa.ForeignKeyConstraint(["owner_npc_id"], ["npc_profiles.id"], name="fk_memories_owner_npc_id_npc_profiles"),
        sa.ForeignKeyConstraint(["source_observation_id"], ["observations.id"], name="fk_memories_source_observation_id_observations"),
        sa.UniqueConstraint("source_observation_id", name="uq_memories_source_observation"),
        sa.UniqueConstraint("world_id", "owner_npc_id", "authored_source_id", "authored_source_version", name="uq_memories_authored_source"),
        sa.CheckConstraint(
            "(memory_type IN ('episodic', 'conversation') AND source_observation_id IS NOT NULL "
            "AND authored_source_id IS NULL AND authored_source_version IS NULL) OR "
            "(memory_type = 'knowledge' AND source_observation_id IS NULL "
            "AND authored_source_id IS NOT NULL AND authored_source_version IS NOT NULL) OR "
            "(memory_type = 'reflection' AND source_observation_id IS NULL "
            "AND authored_source_id IS NULL AND authored_source_version IS NULL)",
            name="ck_memories_source_reference_shape",
        ),
        sa.CheckConstraint("memory_type IN ('episodic', 'conversation', 'reflection', 'knowledge')", name="ck_memories_memory_type"),
        sa.CheckConstraint("occurred_world_version >= 0", name="ck_memories_occurred_world_version"),
        sa.CheckConstraint("occurred_clock_tick >= 0", name="ck_memories_occurred_clock_tick"),
        sa.CheckConstraint("created_world_version >= 0", name="ck_memories_created_world_version"),
        sa.CheckConstraint("created_clock_tick >= 0", name="ck_memories_created_clock_tick"),
        sa.CheckConstraint("importance BETWEEN 0 AND 1", name="ck_memories_importance"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_memories_confidence"),
        sa.CheckConstraint("emotional_valence BETWEEN -1 AND 1", name="ck_memories_emotional_valence"),
        sa.CheckConstraint("secrecy IN ('public', 'private', 'secret')", name="ck_memories_secrecy"),
        sa.CheckConstraint("disclosure_scope IN ('public', 'player_dialogue', 'internal_only')", name="ck_memories_disclosure_scope"),
        sa.CheckConstraint("lifecycle_state IN ('active', 'archived', 'disputed', 'superseded')", name="ck_memories_lifecycle_state"),
        sa.CheckConstraint("embedding_dimensions IS NULL OR embedding_dimensions > 0", name="ck_memories_embedding_dimensions"),
        sa.CheckConstraint("embedding_status IN ('ready', 'failed', 'unavailable')", name="ck_memories_embedding_status"),
        sa.CheckConstraint("access_count >= 0", name="ck_memories_access_count"),
    )
    op.create_index("ix_memories_owner_lifecycle_occurred", "memories", ["world_id", "owner_npc_id", "lifecycle_state", "occurred_clock_tick", "id"])
    op.create_index("ix_memories_embedding_space", "memories", ["embedding_provider", "embedding_model", "embedding_version", "embedding_dimensions"])

    op.create_table(
        "memory_evidence",
        sa.Column("derived_memory_id", sa.String(36), nullable=False),
        sa.Column("evidence_memory_id", sa.String(36), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("derived_memory_id", "evidence_memory_id", name="pk_memory_evidence"),
        sa.ForeignKeyConstraint(["derived_memory_id"], ["memories.id"], name="fk_memory_evidence_derived_memory_id_memories"),
        sa.ForeignKeyConstraint(["evidence_memory_id"], ["memories.id"], name="fk_memory_evidence_evidence_memory_id_memories"),
        sa.UniqueConstraint("derived_memory_id", "ordinal", name="uq_memory_evidence_derived_ordinal"),
        sa.CheckConstraint("ordinal >= 0", name="ck_memory_evidence_ordinal"),
        sa.CheckConstraint("derived_memory_id <> evidence_memory_id", name="ck_memory_evidence_no_self_reference"),
    )

    op.create_table(
        "beliefs",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("world_id", sa.String(), nullable=False),
        sa.Column("owner_npc_id", sa.String(), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("safe_summary", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("lifecycle_state", sa.String(), nullable=False),
        sa.Column("supersedes_belief_id", sa.String(36), nullable=True),
        sa.Column("source_reflection_memory_id", sa.String(36), nullable=False),
        sa.Column("created_world_version", sa.Integer(), nullable=False),
        sa.Column("created_clock_tick", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_beliefs"),
        sa.ForeignKeyConstraint(["world_id"], ["world_state.id"], name="fk_beliefs_world_id_world_state"),
        sa.ForeignKeyConstraint(["owner_npc_id"], ["npc_profiles.id"], name="fk_beliefs_owner_npc_id_npc_profiles"),
        sa.ForeignKeyConstraint(["supersedes_belief_id"], ["beliefs.id"], name="fk_beliefs_supersedes_belief_id_beliefs"),
        sa.ForeignKeyConstraint(["source_reflection_memory_id"], ["memories.id"], name="fk_beliefs_source_reflection_memory_id_memories"),
        sa.UniqueConstraint("source_reflection_memory_id", name="uq_beliefs_source_reflection_memory"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_beliefs_confidence"),
        sa.CheckConstraint("lifecycle_state IN ('active', 'disputed', 'superseded')", name="ck_beliefs_lifecycle_state"),
        sa.CheckConstraint("created_world_version >= 0", name="ck_beliefs_created_world_version"),
        sa.CheckConstraint("created_clock_tick >= 0", name="ck_beliefs_created_clock_tick"),
    )
    op.create_index("ix_beliefs_owner_lifecycle_created", "beliefs", ["world_id", "owner_npc_id", "lifecycle_state", "created_clock_tick", "id"])

    op.create_table(
        "belief_evidence",
        sa.Column("belief_id", sa.String(36), nullable=False),
        sa.Column("memory_id", sa.String(36), nullable=False),
        sa.Column("evidence_role", sa.String(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("belief_id", "memory_id", "evidence_role", name="pk_belief_evidence"),
        sa.ForeignKeyConstraint(["belief_id"], ["beliefs.id"], name="fk_belief_evidence_belief_id_beliefs"),
        sa.ForeignKeyConstraint(["memory_id"], ["memories.id"], name="fk_belief_evidence_memory_id_memories"),
        sa.UniqueConstraint("belief_id", "evidence_role", "ordinal", name="uq_belief_evidence_role_ordinal"),
        sa.CheckConstraint("evidence_role IN ('supporting', 'contradicting')", name="ck_belief_evidence_role"),
        sa.CheckConstraint("ordinal >= 0", name="ck_belief_evidence_ordinal"),
    )


def downgrade() -> None:
    raise RuntimeError("0004 cannot be downgraded without losing cognition provenance")
