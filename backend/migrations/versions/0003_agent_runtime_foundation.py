"""Persist atomic agent runs and factual, ordered domain events."""

from datetime import UTC, datetime
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("world_id", sa.String(), sa.ForeignKey("world_state.id"), nullable=False),
        *[sa.Column(name, sa.String(), nullable=False) for name in ("mode", "trigger_type", "status")],
        *[sa.Column(name, sa.Integer(), nullable=False) for name in ("base_world_version", "resulting_world_version", "base_clock_tick", "resulting_clock_tick")],
        sa.Column("correlation_id", sa.String(36), nullable=False),
        *[sa.Column(name, sa.DateTime(timezone=True), nullable=False) for name in ("created_at", "started_at", "completed_at")],
        sa.Column("error_code", sa.String(), nullable=True),
    )
    op.create_index("ix_agent_runs_world_id", "agent_runs", ["world_id"])
    op.create_table(
        "action_proposals",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("agent_runs.id"), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        *[sa.Column(name, sa.String(), nullable=False) for name in ("actor_id", "action_type", "reason_code", "source", "status")],
        *[sa.Column(name, sa.String(), nullable=True) for name in ("target_kind", "target_id", "rejection_code", "rejection_message")],
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.UniqueConstraint("run_id", "ordinal", name="uq_proposals_run_ordinal"),
    )
    op.create_table(
        "agent_trace_entries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("agent_runs.id"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        *[sa.Column(name, sa.String(), nullable=False) for name in ("stage", "summary", "visibility")],
        sa.Column("actor_id", sa.String(), nullable=True),
        sa.Column("data_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("run_id", "sequence", name="uq_trace_run_sequence"),
    )
    with op.batch_alter_table("actions") as batch:
        for name in ("ck_actions_action_type", "ck_actions_target_kind", "ck_actions_status"):
            batch.drop_constraint(name, type_="check")
        batch.alter_column("reason", new_column_name="reason_code", existing_type=sa.String())
        batch.add_column(sa.Column("run_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("proposal_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("world_version", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_foreign_key("fk_actions_run", "agent_runs", ["run_id"], ["id"])
        batch.create_foreign_key("fk_actions_proposal", "action_proposals", ["proposal_id"], ["id"])
    with op.batch_alter_table("events") as batch:
        batch.drop_constraint("ck_events_event_type", type_="check")
        batch.drop_constraint("ck_events_clock_tick", type_="check")
        batch.create_check_constraint("ck_events_clock_tick", "clock_tick >= 0")
        batch.alter_column("actor_id", existing_type=sa.String(), nullable=True)
        batch.alter_column("action_id", existing_type=sa.Integer(), nullable=True)
        for name, type_ in (
            ("run_id", sa.String(36)), ("world_version", sa.Integer()),
            ("event_sequence", sa.Integer()), ("source_event_id", sa.Integer()),
            ("payload_json", sa.JSON()), ("visibility", sa.String()),
            ("secrecy", sa.String()), ("causation_id", sa.String()),
            ("correlation_id", sa.String(36)), ("created_at", sa.DateTime(timezone=True)),
        ):
            batch.add_column(sa.Column(name, type_, nullable=True))
        batch.create_foreign_key("fk_events_run", "agent_runs", ["run_id"], ["id"])
        batch.create_foreign_key("fk_events_source", "events", ["source_event_id"], ["id"])
        batch.create_unique_constraint("uq_events_world_sequence", ["world_id", "event_sequence"])

    op.execute("UPDATE actions SET action_type = 'talk' WHERE action_type = 'social'")
    op.execute("UPDATE npc_states SET current_action = 'talk' WHERE current_action = 'social'")
    _backfill()
    with op.batch_alter_table("actions") as batch:
        batch.alter_column("world_version", existing_type=sa.Integer(), nullable=False)
        batch.alter_column("created_at", existing_type=sa.DateTime(timezone=True), nullable=False)
    with op.batch_alter_table("events") as batch:
        for name, type_ in (("world_version", sa.Integer()), ("event_sequence", sa.Integer()),
                            ("payload_json", sa.JSON()), ("visibility", sa.String()),
                            ("secrecy", sa.String()), ("correlation_id", sa.String(36)),
                            ("created_at", sa.DateTime(timezone=True))):
            batch.alter_column(name, existing_type=type_, nullable=False)


def _backfill() -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()
    tables = {name: sa.Table(name, metadata, autoload_with=bind) for name in (
        "agent_runs", "action_proposals", "actions", "events", "npc_profiles", "world_state"
    )}
    runs, proposals, actions, events, actors, worlds = (tables[n] for n in tables)
    now = datetime.now(UTC)
    groups = bind.execute(sa.select(actions.c.world_id, actions.c.clock_tick).distinct().order_by(actions.c.world_id, actions.c.clock_tick)).all()
    for world_id, tick in groups:
        run_id, correlation_id = str(uuid4()), str(uuid4())
        bind.execute(runs.insert().values(
            id=run_id, world_id=world_id, mode="deterministic", trigger_type="world_advance", status="completed",
            base_world_version=tick - 1, resulting_world_version=tick,
            base_clock_tick=tick - 1, resulting_clock_tick=tick,
            correlation_id=correlation_id, created_at=now, started_at=now, completed_at=now,
        ))
        ordered = bind.execute(sa.select(actions).join(actors, actions.c.actor_id == actors.c.id).where(
            actions.c.world_id == world_id, actions.c.clock_tick == tick
        ).order_by(actors.c.sort_order, actions.c.actor_id, actions.c.id)).mappings().all()
        for ordinal, action in enumerate(ordered):
            proposal_id = bind.execute(proposals.insert().values(
                run_id=run_id, ordinal=ordinal, actor_id=action["actor_id"], action_type=action["action_type"],
                target_kind=action["target_kind"], target_id=action["target_id"], reason_code=action["reason_code"],
                source="deterministic", status="accepted", payload_json={},
            )).inserted_primary_key[0]
            bind.execute(actions.update().where(actions.c.id == action["id"]).values(
                run_id=run_id, proposal_id=proposal_id, world_version=tick, status="executed", created_at=now,
            ))
            bind.execute(events.update().where(events.c.action_id == action["id"]).values(
                run_id=run_id, correlation_id=correlation_id,
                payload_json={"action_type":action["action_type"], "reason_code":action["reason_code"], "proposal_ordinal":ordinal,
                              "target": {"kind":action["target_kind"], "id":action["target_id"]} if action["target_kind"] else None},
            ))
    for world_id in bind.scalars(sa.select(worlds.c.id)):
        legacy = bind.execute(sa.select(events).where(events.c.world_id == world_id).order_by(events.c.id)).mappings().all()
        for sequence, event in enumerate(legacy, 1):
            bind.execute(events.update().where(events.c.id == event["id"]).values(
                event_sequence=sequence, world_version=event["clock_tick"], visibility="public", secrecy="public",
                created_at=now, payload_json=event["payload_json"] or {}, correlation_id=event["correlation_id"] or str(uuid4()),
            ))
        bind.execute(worlds.update().where(worlds.c.id == world_id).values(event_sequence=len(legacy)))


def downgrade() -> None:
    # New event kinds and rejected proposals have no lossless legacy representation.
    raise RuntimeError("0003 cannot be downgraded without losing runtime history")
