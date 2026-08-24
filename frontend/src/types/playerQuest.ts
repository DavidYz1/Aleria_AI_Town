export type QuestStatus =
  | 'available'
  | 'accepted'
  | 'briefed_by_grey'
  | 'shoe_found'
  | 'child_found'
  | 'completed'

export type QuestInteraction =
  | 'accept_quest'
  | 'ask_grey'
  | 'inspect_shoe'
  | 'search_child'
  | 'return_child'

export interface PlayerData {
  id: string
  location_id: string
  location_name: string
}

export interface QuestInteractionData {
  id: QuestInteraction
  label: string
}

export interface QuestEventData {
  id: number
  from_status: QuestStatus
  to_status: QuestStatus
  interaction: QuestInteraction
  description: string
}

export interface QuestData {
  id: 'missing-child'
  title: string
  status: QuestStatus
  version: number
  objective: string
  available_interactions: QuestInteractionData[]
  recent_events: QuestEventData[]
}

export interface PlayerQuestData {
  player: PlayerData
  quest: QuestData
}

export interface QuestInteractRequest {
  interaction: QuestInteraction
  expected_version: number
}

export type PlayerQuestFetcher = () => Promise<PlayerQuestData>
export type PlayerTraveller = (locationId: string) => Promise<PlayerQuestData>
export type QuestInteractor = (
  request: QuestInteractRequest,
) => Promise<PlayerQuestData>
