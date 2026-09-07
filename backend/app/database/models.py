from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
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
        Index(
            "ix_conversation_messages_conversation_id_id",
            "conversation_id",
            "id",
        ),
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
