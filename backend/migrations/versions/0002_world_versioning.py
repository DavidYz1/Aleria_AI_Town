"""split world version, clock tick, and event sequence"""

from alembic import op
import sqlalchemy as sa


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _normalized_check_sql(constraint: sa.CheckConstraint) -> str:
    rendered = str(constraint.sqltext).lower()
    return "".join(
        character for character in rendered if character not in " \t\r\n()\"`"
    )


def _sqlite_copy_from_without_obsolete_constraints(
    table_name: str,
    *,
    check_sql: frozenset[str] = frozenset(),
    unique_columns: frozenset[tuple[str, ...]] = frozenset(),
    preserved_check_names: tuple[tuple[str, str], ...] = (),
) -> sa.Table:
    bind = op.get_bind()
    table = sa.Table(table_name, sa.MetaData(), autoload_with=bind)
    removed_checks: set[str] = set()
    removed_uniques: set[tuple[str, ...]] = set()
    preserved_names = dict(preserved_check_names)
    found_preserved_checks: set[str] = set()
    for constraint in tuple(table.constraints):
        if isinstance(constraint, sa.CheckConstraint):
            normalized = _normalized_check_sql(constraint)
            if normalized in check_sql:
                table.constraints.remove(constraint)
                removed_checks.add(normalized)
            elif normalized in preserved_names:
                found_preserved_checks.add(normalized)
                if constraint.name is None:
                    constraint.name = preserved_names[normalized]
        elif isinstance(constraint, sa.UniqueConstraint):
            columns = tuple(column.name for column in constraint.columns)
            if columns in unique_columns:
                table.constraints.remove(constraint)
                removed_uniques.add(columns)
    if (
        removed_checks != set(check_sql)
        or removed_uniques != set(unique_columns)
        or found_preserved_checks != set(preserved_names)
    ):
        raise RuntimeError(f"unsupported legacy constraints for {table_name}")
    return table


def _rename_columns() -> None:
    sqlite = op.get_bind().dialect.name == "sqlite"
    world_state = (
        _sqlite_copy_from_without_obsolete_constraints(
            "world_state", check_sql=frozenset({"tick>=0"})
        )
        if sqlite
        else None
    )
    with op.batch_alter_table("world_state", copy_from=world_state) as batch:
        if not sqlite:
            batch.drop_constraint("ck_world_state_tick", type_="check")
        batch.alter_column("tick", new_column_name="clock_tick", existing_type=sa.Integer())
        batch.add_column(sa.Column("world_version", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("event_sequence", sa.Integer(), nullable=True))
        batch.create_check_constraint("ck_world_state_clock_tick", "clock_tick >= 0")
        batch.create_check_constraint("ck_world_state_world_version", "world_version >= 0")
        batch.create_check_constraint("ck_world_state_event_sequence", "event_sequence >= 0")
    quest_progress = (
        _sqlite_copy_from_without_obsolete_constraints(
            "quest_progress", check_sql=frozenset({"updated_tick>=0"})
        )
        if sqlite
        else None
    )
    with op.batch_alter_table("quest_progress", copy_from=quest_progress) as batch:
        if not sqlite:
            batch.drop_constraint("ck_quest_progress_updated_tick", type_="check")
        batch.alter_column("updated_tick", new_column_name="updated_clock_tick", existing_type=sa.Integer())
        batch.create_check_constraint("ck_quest_progress_updated_clock_tick", "updated_clock_tick >= 0")
    quest_events = (
        _sqlite_copy_from_without_obsolete_constraints(
            "quest_events", check_sql=frozenset({"world_tick>=0"})
        )
        if sqlite
        else None
    )
    with op.batch_alter_table("quest_events", copy_from=quest_events) as batch:
        if not sqlite:
            batch.drop_constraint("ck_quest_events_world_tick", type_="check")
        batch.alter_column("world_tick", new_column_name="clock_tick", existing_type=sa.Integer())
        batch.create_check_constraint("ck_quest_events_clock_tick", "clock_tick >= 0")
    actions = (
        _sqlite_copy_from_without_obsolete_constraints(
            "actions",
            check_sql=frozenset({"tick>=1"}),
            unique_columns=frozenset({("world_id", "tick", "actor_id")}),
            preserved_check_names=(
                (
                    "action_typein'move','rest','work','eat','social'",
                    "ck_actions_action_type",
                ),
                (
                    "target_kindisnullortarget_kindin'location','npc'",
                    "ck_actions_target_kind",
                ),
                ("status='recorded'", "ck_actions_status"),
            ),
        )
        if sqlite
        else None
    )
    with op.batch_alter_table("actions", copy_from=actions) as batch:
        if not sqlite:
            batch.drop_constraint("ck_actions_tick", type_="check")
            batch.drop_constraint("uq_actions_world_tick_actor", type_="unique")
        batch.drop_index("ix_actions_actor_tick")
        batch.alter_column("tick", new_column_name="clock_tick", existing_type=sa.Integer())
        batch.create_check_constraint("ck_actions_clock_tick", "clock_tick >= 1")
    op.create_index("ix_actions_actor_clock_tick", "actions", ["actor_id", "clock_tick"])
    actions_with_clock_tick = (
        _sqlite_copy_from_without_obsolete_constraints("actions")
        if sqlite
        else None
    )
    with op.batch_alter_table(
        "actions", copy_from=actions_with_clock_tick
    ) as batch:
        batch.create_unique_constraint(
            "uq_actions_world_clock_tick_actor",
            ["world_id", "clock_tick", "actor_id"],
        )
    events = (
        _sqlite_copy_from_without_obsolete_constraints(
            "events",
            check_sql=frozenset({"tick>=1"}),
            preserved_check_names=(
                ("event_type='npc_action'", "ck_events_event_type"),
            ),
        )
        if sqlite
        else None
    )
    with op.batch_alter_table("events", copy_from=events) as batch:
        if not sqlite:
            batch.drop_constraint("ck_events_tick", type_="check")
        batch.drop_index("ix_events_actor_tick")
        batch.alter_column("tick", new_column_name="clock_tick", existing_type=sa.Integer())
        batch.create_check_constraint("ck_events_clock_tick", "clock_tick >= 1")
    op.create_index("ix_events_actor_clock_tick", "events", ["actor_id", "clock_tick"])
    conversations = (
        _sqlite_copy_from_without_obsolete_constraints(
            "conversations", check_sql=frozenset({"created_tick>=0"})
        )
        if sqlite
        else None
    )
    with op.batch_alter_table("conversations", copy_from=conversations) as batch:
        if not sqlite:
            batch.drop_constraint("ck_conversations_created_tick", type_="check")
        batch.alter_column("created_tick", new_column_name="created_clock_tick", existing_type=sa.Integer())
        batch.create_check_constraint("ck_conversations_created_clock_tick", "created_clock_tick >= 0")
    conversation_messages = (
        _sqlite_copy_from_without_obsolete_constraints(
            "conversation_messages", check_sql=frozenset({"world_tick>=0"})
        )
        if sqlite
        else None
    )
    with op.batch_alter_table(
        "conversation_messages", copy_from=conversation_messages
    ) as batch:
        if not sqlite:
            batch.drop_constraint("ck_conversation_messages_world_tick", type_="check")
        batch.alter_column("world_tick", new_column_name="clock_tick", existing_type=sa.Integer())
        batch.create_check_constraint("ck_conversation_messages_clock_tick", "clock_tick >= 0")


def upgrade() -> None:
    dialect_name = op.get_bind().dialect.name
    sqlite = dialect_name == "sqlite"
    if dialect_name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    _rename_columns()
    op.execute("UPDATE world_state SET world_version = clock_tick, event_sequence = (SELECT count(*) FROM events WHERE events.world_id = world_state.id)")
    world_state = (
        _sqlite_copy_from_without_obsolete_constraints("world_state")
        if sqlite
        else None
    )
    with op.batch_alter_table("world_state", copy_from=world_state) as batch:
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
