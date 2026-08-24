from typing import cast

from backend.app.database.player_quest_repository import (
    PlayerNotFoundError,
    PlayerQuestPersistenceError,
    PlayerQuestRepository,
    QuestNotFoundError,
)
from backend.app.llm.types import PlayerQuestChatContext
from backend.app.quests.missing_child import MissingChildQuestPolicy
from backend.app.quests.types import QuestStatus


class PlayerQuestChatContextReader:
    PLAYER_ID = "default-player"
    QUEST_ID = "missing-child"

    def __init__(
        self,
        repository: PlayerQuestRepository,
        policy: MissingChildQuestPolicy,
    ) -> None:
        self._repository = repository
        self._policy = policy

    def get_chat_context(self) -> PlayerQuestChatContext | None:
        try:
            records = self._repository.get_state(
                self.PLAYER_ID,
                self.QUEST_ID,
            )
            presentation = self._policy.present(
                cast(QuestStatus, records.status),
                records.location_id,
                target_npc_location_id=records.target_npc_location_id,
                target_npc_location_name=records.target_npc_location_name,
            )
            return PlayerQuestChatContext(
                player_id=records.player_id,
                location_id=records.location_id,
                location_name=records.location_name,
                quest_id=records.quest_id,
                quest_status=records.status,
                quest_objective=presentation.objective,
            )
        except (
            PlayerNotFoundError,
            QuestNotFoundError,
            PlayerQuestPersistenceError,
            KeyError,
        ):
            return None
