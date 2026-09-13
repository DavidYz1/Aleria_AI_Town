"""Add Stage 3m agent plans table (procedural memory)."""

from alembic import op
import sqlalchemy as sa


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_plans",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("world_id", sa.String(), nullable=False),
        sa.Column("owner_npc_id", sa.String(), nullable=False),
        sa.Column("source_run_id", sa.String(36), nullable=True),
        sa.Column("thought", sa.String(800), nullable=False),
        sa.Column("goal", sa.String(200), nullable=False),
        sa.Column("goal_reason", sa.String(500), nullable=False),
        sa.Column("steps_json", sa.JSON(), nullable=False),
        sa.Column("current_step_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("created_clock_tick", sa.Integer(), nullable=False),
        sa.Column("updated_clock_tick", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("prompt_version", sa.String(40), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_agent_plans"),
        sa.ForeignKeyConstraint(["world_id"], ["world_state.id"], name="fk_agent_plans_world_id_world_state"),
        sa.ForeignKeyConstraint(["owner_npc_id"], ["npc_profiles.id"], name="fk_agent_plans_owner_npc_id_npc_profiles"),
        sa.ForeignKeyConstraint(["source_run_id"], ["agent_runs.id"], name="fk_agent_plans_source_run_id_agent_runs"),
        sa.CheckConstraint("status IN ('active', 'completed', 'abandoned')", name="ck_agent_plans_status"),
        sa.CheckConstraint("current_step_index >= 0", name="ck_agent_plans_current_step_index"),
    )
    op.create_index(
        "ix_agent_plans_owner_status",
        "agent_plans",
        ["world_id", "owner_npc_id", "status", "created_clock_tick"],
    )
    # 单 NPC 至多一条活跃计划。SQLite 与 PostgreSQL 均支持 partial unique index。
    op.create_index(
        "uq_agent_plans_active",
        "agent_plans",
        ["world_id", "owner_npc_id"],
        unique=True,
        sqlite_where=sa.text("status = 'active'"),
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index("uq_agent_plans_active", table_name="agent_plans")
    op.drop_index("ix_agent_plans_owner_status", table_name="agent_plans")
    op.drop_table("agent_plans")
