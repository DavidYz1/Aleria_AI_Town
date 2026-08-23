from sqlalchemy import CheckConstraint, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class WorldState(Base):
    __tablename__ = "world_state"
    __table_args__ = (
        CheckConstraint("day >= 1"),
        CheckConstraint("tick >= 0"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    day: Mapped[int] = mapped_column(Integer, nullable=False)
    time: Mapped[str] = mapped_column(String(5), nullable=False)
    tick: Mapped[int] = mapped_column(Integer, nullable=False)


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
