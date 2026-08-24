from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.app.quests.types import QuestInteraction, QuestStatus
from backend.app.schemas.player import PlayerData


class QuestInteractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interaction: QuestInteraction
    expected_version: int = Field(ge=0)


class QuestInteractionData(BaseModel):
    id: QuestInteraction
    label: str


class QuestEventData(BaseModel):
    id: int
    from_status: QuestStatus
    to_status: QuestStatus
    interaction: QuestInteraction
    description: str


class QuestData(BaseModel):
    id: Literal["missing-child"]
    title: str
    status: QuestStatus
    version: int = Field(ge=0)
    objective: str
    available_interactions: list[QuestInteractionData]
    recent_events: list[QuestEventData]


class PlayerQuestData(BaseModel):
    player: PlayerData
    quest: QuestData
