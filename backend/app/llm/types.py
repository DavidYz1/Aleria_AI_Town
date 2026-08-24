from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class PromptBundle:
    world_lore: str
    chat_system_prompt: str
    player_context: str
    character_prompt: str


@dataclass(frozen=True)
class ChatHistoryMessage:
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True)
class ChatActionContext:
    tick: int
    world_time: str
    action_type: str
    target_name: str | None
    reason_code: str


@dataclass(frozen=True)
class PlayerQuestChatContext:
    player_id: str
    location_id: str
    location_name: str
    quest_id: str
    quest_status: str
    quest_objective: str


@dataclass(frozen=True)
class PlayerProfileChatContext:
    display_name: str
    adventurer_class: Literal["mage", "ranger", "cleric"]
    class_title: str


@dataclass(frozen=True)
class ChatProviderRequest:
    npc_id: str
    npc_name: str
    role: str
    personality: tuple[str, ...]
    character_prompt: str
    world_lore: str
    chat_system_prompt: str
    player_context_prompt: str
    world_id: str
    world_name: str
    world_day: int
    world_time: str
    world_tick: int
    time_phase: Literal["morning", "day", "evening", "night"]
    location_id: str
    location_name: str
    current_action: str
    energy: int
    mood: int
    social: int
    recent_actions: tuple[ChatActionContext, ...]
    player_quest_context: PlayerQuestChatContext | None
    conversation_history: tuple[ChatHistoryMessage, ...]
    player_message: str
    player_profile: PlayerProfileChatContext | None = None
