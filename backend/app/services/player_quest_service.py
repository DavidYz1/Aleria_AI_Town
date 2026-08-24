from typing import cast

from pydantic import ValidationError

from backend.app.database.player_quest_repository import (
    PlayerQuestRecords,
    PlayerQuestRepository,
)
from backend.app.quests.missing_child import MissingChildQuestPolicy
from backend.app.quests.types import (
    QuestCommand,
    QuestInteraction,
    QuestSnapshot,
    QuestStatus,
)
from backend.app.schemas.player import PlayerData, PlayerTravelRequest
from backend.app.schemas.quest import (
    PlayerQuestData,
    QuestData,
    QuestEventData,
    QuestInteractRequest,
    QuestInteractionData,
)


class PlayerQuestServiceUnavailableError(RuntimeError):
    pass


class PlayerQuestService:
    PLAYER_ID = "default-player"
    QUEST_ID = "missing-child"

    _EVENT_DESCRIPTIONS = {
        "accept_quest": "你在星辉酒馆接受了寻找失踪孩子的委托。",
        "ask_grey": "Grey 告诉你，孩子最后可能前往了低语森林。",
        "inspect_shoe": "你在低语森林发现了一只遗落的鞋子。",
        "search_child": "你沿着痕迹找到了失踪的孩子。",
        "return_child": "你把孩子安全带回星辉酒馆，完成了委托。",
    }

    def __init__(
        self,
        repository: PlayerQuestRepository,
        policy: MissingChildQuestPolicy,
    ) -> None:
        self._repository = repository
        self._policy = policy

    def get_state(self) -> PlayerQuestData:
        return self._to_data(
            self._repository.get_state(self.PLAYER_ID, self.QUEST_ID)
        )

    def travel(self, request: PlayerTravelRequest) -> PlayerQuestData:
        return self._to_data(
            self._repository.travel(
                self.PLAYER_ID,
                self.QUEST_ID,
                request.target_location_id,
            )
        )

    def interact(self, request: QuestInteractRequest) -> PlayerQuestData:
        records = self._repository.get_state(self.PLAYER_ID, self.QUEST_ID)
        transition = self._policy.transition(
            QuestSnapshot(
                quest_id=records.quest_id,
                status=cast(QuestStatus, records.status),
                version=records.version,
                player_location_id=records.location_id,
                world_tick=records.world_tick,
            ),
            QuestCommand(
                interaction=request.interaction,
                expected_version=request.expected_version,
            ),
        )
        return self._to_data(
            self._repository.apply_transition(
                player_id=self.PLAYER_ID,
                quest_id=self.QUEST_ID,
                expected_version=request.expected_version,
                transition=transition,
            )
        )

    def _to_data(self, records: PlayerQuestRecords) -> PlayerQuestData:
        try:
            status = cast(QuestStatus, records.status)
            presentation = self._policy.present(
                status,
                records.location_id,
            )
            return PlayerQuestData(
                player=PlayerData(
                    id=records.player_id,
                    location_id=records.location_id,
                    location_name=records.location_name,
                ),
                quest=QuestData(
                    id="missing-child",
                    title=presentation.title,
                    status=status,
                    version=records.version,
                    objective=presentation.objective,
                    available_interactions=[
                        QuestInteractionData(
                            id=interaction.id,
                            label=interaction.label,
                        )
                        for interaction in presentation.available_interactions
                    ],
                    recent_events=[
                        QuestEventData(
                            id=event.id,
                            from_status=cast(
                                QuestStatus,
                                event.from_status,
                            ),
                            to_status=cast(QuestStatus, event.to_status),
                            interaction=cast(
                                QuestInteraction,
                                event.interaction,
                            ),
                            description=self._EVENT_DESCRIPTIONS[
                                event.interaction
                            ],
                        )
                        for event in records.recent_events
                    ],
                ),
            )
        except (KeyError, ValidationError):
            raise PlayerQuestServiceUnavailableError(
                "Player quest service is unavailable"
            ) from None
