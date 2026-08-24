import type { AdventurerClass } from '../player/playerProfile'


export type ChatEmotion =
  | 'neutral'
  | 'cheerful'
  | 'reserved'
  | 'guarded'
  | 'thoughtful'
  | 'concerned'

export interface NpcChatPlayerProfile {
  display_name: string
  adventurer_class: AdventurerClass
}

export interface NpcChatRequest {
  conversation_id: string | null
  message: string
  player_profile?: NpcChatPlayerProfile
}

export interface ChatUserMessage {
  id: number
  role: 'user'
  content: string
}

export interface ChatAssistantMessage {
  id: number
  role: 'assistant'
  content: string
  emotion: ChatEmotion
}

export type ChatMessage = ChatUserMessage | ChatAssistantMessage

export interface NpcChatData {
  conversation_id: string
  npc_id: string
  turn: {
    user: ChatUserMessage
    assistant: ChatAssistantMessage
  }
  provider: string
  fallback_used: boolean
}

export type ChatFetcher = (
  npcId: string,
  request: NpcChatRequest,
) => Promise<NpcChatData>
