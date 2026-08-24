from dataclasses import dataclass
from datetime import UTC, datetime
import logging

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.database.models import (
    Location,
    NpcState,
    PlayerState,
    QuestEvent,
    QuestProgress,
    WorldState,
)
from backend.app.quests.types import (
    QuestInteractionUnavailableError,
    QuestStateConflictError,
    QuestTransition,
)


logger = logging.getLogger(__name__)


class PlayerNotFoundError(RuntimeError):
    pass


class LocationNotFoundError(RuntimeError):
    pass


class QuestNotFoundError(RuntimeError):
    pass


class PlayerQuestPersistenceError(RuntimeError):
    pass


@dataclass(frozen=True)
class QuestEventRecord:
    id: int
    from_status: str
    to_status: str
    interaction: str
    location_id: str
    world_tick: int


@dataclass(frozen=True)
class PlayerQuestRecords:
    player_id: str
    world_id: str
    location_id: str
    location_name: str
    quest_id: str
    status: str
    version: int
    updated_tick: int
    world_tick: int
    target_npc_location_id: str
    target_npc_location_name: str
    recent_events: tuple[QuestEventRecord, ...]


class PlayerQuestRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_state(
        self,
        player_id: str,
        quest_id: str,
    ) -> PlayerQuestRecords:
        try:
            player = self._session.get(PlayerState, player_id)
            if player is None:
                raise PlayerNotFoundError("Player not found")

            progress = self._session.get(
                QuestProgress,
                (player_id, quest_id),
            )
            if progress is None:
                raise QuestNotFoundError("Quest not found")

            location = self._session.get(Location, player.location_id)
            world = self._session.get(WorldState, player.world_id)
            target_npc = self._session.get(NpcState, "grey")
            target_npc_location = (
                self._session.get(Location, target_npc.location_id)
                if target_npc is not None
                else None
            )
            if (
                location is None
                or world is None
                or target_npc is None
                or target_npc_location is None
            ):
                raise PlayerQuestPersistenceError(
                    "Player quest service is unavailable"
                )

            stored_events = tuple(
                self._session.scalars(
                    select(QuestEvent)
                    .where(
                        QuestEvent.player_id == player_id,
                        QuestEvent.quest_id == quest_id,
                    )
                    .order_by(QuestEvent.id.desc())
                    .limit(5)
                )
            )
            recent_events = tuple(
                QuestEventRecord(
                    id=event.id,
                    from_status=event.from_status,
                    to_status=event.to_status,
                    interaction=event.interaction,
                    location_id=event.location_id,
                    world_tick=event.world_tick,
                )
                for event in reversed(stored_events)
            )
            return PlayerQuestRecords(
                player_id=player.id,
                world_id=player.world_id,
                location_id=player.location_id,
                location_name=location.name,
                quest_id=progress.quest_id,
                status=progress.status,
                version=progress.version,
                updated_tick=progress.updated_tick,
                world_tick=world.tick,
                target_npc_location_id=target_npc.location_id,
                target_npc_location_name=target_npc_location.name,
                recent_events=recent_events,
            )
        except (
            PlayerNotFoundError,
            QuestNotFoundError,
            PlayerQuestPersistenceError,
        ):
            raise
        except SQLAlchemyError:
            self._log_failure("read", player_id, quest_id)
            raise PlayerQuestPersistenceError(
                "Player quest service is unavailable"
            ) from None

    def travel(
        self,
        player_id: str,
        quest_id: str,
        target_location_id: str,
    ) -> PlayerQuestRecords:
        try:
            records = self.get_state(player_id, quest_id)
            target = self._session.get(Location, target_location_id)
            if target is None:
                raise LocationNotFoundError("Location not found")
            if records.location_id == target_location_id:
                return records

            player = self._session.get(PlayerState, player_id)
            if player is None:
                raise PlayerNotFoundError("Player not found")
            player.location_id = target_location_id
            player.updated_at = datetime.now(UTC)
            self._session.commit()
            return self.get_state(player_id, quest_id)
        except (
            PlayerNotFoundError,
            LocationNotFoundError,
            QuestNotFoundError,
            PlayerQuestPersistenceError,
        ):
            self._session.rollback()
            raise
        except SQLAlchemyError:
            self._session.rollback()
            self._log_failure("travel", player_id, quest_id)
            raise PlayerQuestPersistenceError(
                "Player quest service is unavailable"
            ) from None

    def apply_transition(
        self,
        *,
        player_id: str,
        quest_id: str,
        expected_version: int,
        transition: QuestTransition,
    ) -> PlayerQuestRecords:
        try:
            player = self._session.get(PlayerState, player_id)
            if player is None:
                raise PlayerNotFoundError("Player not found")
            progress = self._session.get(
                QuestProgress,
                (player_id, quest_id),
                populate_existing=True,
            )
            if progress is None:
                raise QuestNotFoundError("Quest not found")
            world = self._session.get(
                WorldState,
                player.world_id,
                populate_existing=True,
            )
            if world is None:
                raise PlayerQuestPersistenceError(
                    "Player quest service is unavailable"
                )
            if player.location_id != transition.location_id:
                raise QuestInteractionUnavailableError(
                    "Quest interaction is not available"
                )
            if transition.required_npc_id is not None:
                target_npc = self._session.get(
                    NpcState,
                    transition.required_npc_id,
                    populate_existing=True,
                )
                if target_npc is None:
                    raise PlayerQuestPersistenceError(
                        "Player quest service is unavailable"
                    )
                if target_npc.location_id != player.location_id:
                    raise QuestInteractionUnavailableError(
                        "Quest interaction is not available"
                    )

            now = datetime.now(UTC)
            updated = self._session.execute(
                update(QuestProgress)
                .where(
                    QuestProgress.player_id == player_id,
                    QuestProgress.quest_id == quest_id,
                    QuestProgress.version == expected_version,
                    QuestProgress.status == transition.from_status,
                )
                .values(
                    status=transition.to_status,
                    version=expected_version + 1,
                    updated_tick=world.tick,
                    updated_at=now,
                )
            )
            if updated.rowcount != 1:
                raise QuestStateConflictError("Quest state has changed")

            self._session.add(
                QuestEvent(
                    player_id=player_id,
                    quest_id=quest_id,
                    from_status=transition.from_status,
                    to_status=transition.to_status,
                    interaction=transition.interaction,
                    location_id=player.location_id,
                    world_tick=world.tick,
                    created_at=now,
                )
            )
            self._session.commit()
            return self.get_state(player_id, quest_id)
        except (
            PlayerNotFoundError,
            QuestNotFoundError,
            QuestStateConflictError,
            QuestInteractionUnavailableError,
            PlayerQuestPersistenceError,
        ):
            self._session.rollback()
            raise
        except SQLAlchemyError:
            self._session.rollback()
            self._log_failure("transition", player_id, quest_id)
            raise PlayerQuestPersistenceError(
                "Player quest service is unavailable"
            ) from None

    @staticmethod
    def _log_failure(category: str, player_id: str, quest_id: str) -> None:
        logger.warning(
            "Player quest persistence failed category=%s player=%s quest=%s",
            category,
            player_id,
            quest_id,
            extra={
                "category": category,
                "player_id": player_id,
                "quest_id": quest_id,
            },
        )
