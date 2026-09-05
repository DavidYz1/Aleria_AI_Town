"""split world version, clock tick, and event sequence"""

from alembic import op
import sqlalchemy as sa


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _rename_columns() -> None:
    with op.batch_alter_table("world_state") as batch:
        batch.drop_constraint("ck_world_state_tick", type_="check")
        batch.alter_column("tick", new_column_name="clock_tick", existing_type=sa.Integer())
        batch.add_column(sa.Column("world_version", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("event_sequence", sa.Integer(), nullable=True))
        batch.create_check_constraint("ck_world_state_clock_tick", "clock_tick >= 0")
        batch.create_check_constraint("ck_world_state_world_version", "world_version >= 0")
        batch.create_check_constraint("ck_world_state_event_sequence", "event_sequence >= 0")
    with op.batch_alter_table("quest_progress") as batch:
        batch.drop_constraint("ck_quest_progress_updated_tick", type_="check")
        batch.alter_column("updated_tick", new_column_name="updated_clock_tick", existing_type=sa.Integer())
        batch.create_check_constraint("ck_quest_progress_updated_clock_tick", "updated_clock_tick >= 0")
    with op.batch_alter_table("quest_events") as batch:
        batch.drop_constraint("ck_quest_events_world_tick", type_="check")
        batch.alter_column("world_tick", new_column_name="clock_tick", existing_type=sa.Integer())
        batch.create_check_constraint("ck_quest_events_clock_tick", "clock_tick >= 0")
    with op.batch_alter_table("actions") as batch:
        batch.drop_constraint("ck_actions_tick", type_="check")
        batch.drop_constraint("uq_actions_world_tick_actor", type_="unique")
        batch.drop_index("ix_actions_actor_tick")
        batch.alter_column("tick", new_column_name="clock_tick", existing_type=sa.Integer())
        batch.create_check_constraint("ck_actions_clock_tick", "clock_tick >= 1")
    op.create_index("ix_actions_actor_clock_tick", "actions", ["actor_id", "clock_tick"])
    with op.batch_alter_table("actions") as batch:
        batch.create_unique_constraint(
            "uq_actions_world_clock_tick_actor",
            ["world_id", "clock_tick", "actor_id"],
        )
    with op.batch_alter_table("events") as batch:
        batch.drop_constraint("ck_events_tick", type_="check")
        batch.drop_index("ix_events_actor_tick")
        batch.alter_column("tick", new_column_name="clock_tick", existing_type=sa.Integer())
        batch.create_check_constraint("ck_events_clock_tick", "clock_tick >= 1")
    op.create_index("ix_events_actor_clock_tick", "events", ["actor_id", "clock_tick"])
    with op.batch_alter_table("conversations") as batch:
        batch.drop_constraint("ck_conversations_created_tick", type_="check")
        batch.alter_column("created_tick", new_column_name="created_clock_tick", existing_type=sa.Integer())
        batch.create_check_constraint("ck_conversations_created_clock_tick", "created_clock_tick >= 0")
    with op.batch_alter_table("conversation_messages") as batch:
        batch.drop_constraint("ck_conversation_messages_world_tick", type_="check")
        batch.alter_column("world_tick", new_column_name="clock_tick", existing_type=sa.Integer())
        batch.create_check_constraint("ck_conversation_messages_clock_tick", "clock_tick >= 0")


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    _rename_columns()
    op.execute("UPDATE world_state SET world_version = clock_tick, event_sequence = (SELECT count(*) FROM events WHERE events.world_id = world_state.id)")
    with op.batch_alter_table("world_state") as batch:
        batch.alter_column("world_version", nullable=False, existing_type=sa.Integer())
        batch.alter_column("event_sequence", nullable=False, existing_type=sa.Integer())


def downgrade() -> None:
    with op.batch_alter_table("conversation_messages") as batch:
        batch.drop_constraint("ck_conversation_messages_clock_tick", type_="check")
        batch.alter_column("clock_tick", new_column_name="world_tick", existing_type=sa.Integer())
        batch.create_check_constraint("ck_conversation_messages_world_tick", "world_tick >= 0")
    with op.batch_alter_table("conversations") as batch:
        batch.drop_constraint("ck_conversations_created_clock_tick", type_="check")
        batch.alter_column("created_clock_tick", new_column_name="created_tick", existing_type=sa.Integer())
        batch.create_check_constraint("ck_conversations_created_tick", "created_tick >= 0")
    with op.batch_alter_table("events") as batch:
        batch.drop_constraint("ck_events_clock_tick", type_="check")
        batch.drop_index("ix_events_actor_clock_tick")
        batch.alter_column("clock_tick", new_column_name="tick", existing_type=sa.Integer())
        batch.create_check_constraint("ck_events_tick", "tick >= 1")
    op.create_index("ix_events_actor_tick", "events", ["actor_id", "tick"])
    with op.batch_alter_table("actions") as batch:
        batch.drop_constraint("ck_actions_clock_tick", type_="check")
        batch.drop_constraint("uq_actions_world_clock_tick_actor", type_="unique")
        batch.drop_index("ix_actions_actor_clock_tick")
        batch.alter_column("clock_tick", new_column_name="tick", existing_type=sa.Integer())
        batch.create_check_constraint("ck_actions_tick", "tick >= 1")
    op.create_index("ix_actions_actor_tick", "actions", ["actor_id", "tick"])
    with op.batch_alter_table("actions") as batch:
        batch.create_unique_constraint(
            "uq_actions_world_tick_actor",
            ["world_id", "tick", "actor_id"],
        )
    with op.batch_alter_table("quest_events") as batch:
        batch.drop_constraint("ck_quest_events_clock_tick", type_="check")
        batch.alter_column("clock_tick", new_column_name="world_tick", existing_type=sa.Integer())
        batch.create_check_constraint("ck_quest_events_world_tick", "world_tick >= 0")
    with op.batch_alter_table("quest_progress") as batch:
        batch.drop_constraint("ck_quest_progress_updated_clock_tick", type_="check")
        batch.alter_column("updated_clock_tick", new_column_name="updated_tick", existing_type=sa.Integer())
        batch.create_check_constraint("ck_quest_progress_updated_tick", "updated_tick >= 0")
    with op.batch_alter_table("world_state") as batch:
        batch.drop_constraint("ck_world_state_clock_tick", type_="check")
        batch.drop_constraint("ck_world_state_world_version", type_="check")
        batch.drop_constraint("ck_world_state_event_sequence", type_="check")
        batch.drop_column("event_sequence")
        batch.drop_column("world_version")
        batch.alter_column("clock_tick", new_column_name="tick", existing_type=sa.Integer())
        batch.create_check_constraint("ck_world_state_tick", "tick >= 0")
