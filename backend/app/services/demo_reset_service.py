import json
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.database.models import (
    Conversation,
    ConversationMessage,
    Event,
    Location,
    NpcProfile,
    NpcState,
    PlayerState,
    QuestEvent,
    QuestProgress,
    WorldAction,
    WorldState,
)
from backend.app.schemas.demo import DemoResetData
from backend.app.schemas.seed import SeedData


class DemoResetPersistenceError(RuntimeError):
    pass


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_seed_data(seed_dir: Path) -> SeedData:
    return SeedData.model_validate(
        {
            "world": _read_json(seed_dir / "world.json"),
            "locations": _read_json(seed_dir / "locations.json"),
            "npcs": _read_json(seed_dir / "npcs.json"),
        }
    )


class DemoResetService:
    def __init__(self, session: Session):
        self._session = session

    def reset(self, seed: SeedData) -> DemoResetData:
        try:
            self._reset(seed)
            self._session.commit()
        except SQLAlchemyError as exc:
            self._session.rollback()
            raise DemoResetPersistenceError(
                "Demo reset could not be persisted"
            ) from exc

        return DemoResetData(
            world_id=seed.world.id,
            world_tick=seed.world.tick,
            player_location_id="tavern",
            quest_status="available",
        )

    def _reset(self, seed: SeedData) -> None:
        player_ids = select(PlayerState.id).where(
            PlayerState.world_id == seed.world.id
        )
        self._session.execute(
            delete(QuestEvent).where(QuestEvent.player_id.in_(player_ids))
        )
        self._session.execute(
            delete(QuestProgress).where(
                QuestProgress.player_id.in_(player_ids)
            )
        )
        self._session.execute(
            delete(PlayerState).where(PlayerState.world_id == seed.world.id)
        )

        conversation_ids = select(Conversation.id).where(
            Conversation.world_id == seed.world.id
        )
        self._session.execute(
            delete(ConversationMessage).where(
                ConversationMessage.conversation_id.in_(conversation_ids)
            )
        )
        self._session.execute(
            delete(Conversation).where(Conversation.world_id == seed.world.id)
        )
        self._session.execute(
            delete(Event).where(Event.world_id == seed.world.id)
        )
        self._session.execute(
            delete(WorldAction).where(WorldAction.world_id == seed.world.id)
        )

        self._session.merge(WorldState(**seed.world.model_dump()))
        for location in seed.locations:
            self._session.merge(Location(**location.model_dump()))
        for npc in seed.npcs:
            self._session.merge(
                NpcProfile(
                    id=npc.id,
                    name=npc.name,
                    role=npc.role,
                    personality_json=npc.personality,
                    sort_order=npc.sort_order,
                )
            )
        self._session.flush()
        for npc in seed.npcs:
            self._session.merge(
                NpcState(npc_id=npc.id, **npc.state.model_dump())
            )

        self._session.merge(
            PlayerState(
                id="default-player",
                world_id=seed.world.id,
                location_id="tavern",
            )
        )
        self._session.flush()
        self._session.merge(
            QuestProgress(
                player_id="default-player",
                quest_id="missing-child",
                status="available",
                version=0,
                updated_tick=seed.world.tick,
            )
        )
