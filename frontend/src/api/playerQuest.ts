import axios from 'axios'

import { api } from './client'
import type {
  PlayerQuestData,
  PlayerQuestFetcher,
  PlayerTraveller,
  QuestInteractRequest,
  QuestInteractor,
} from '../types/playerQuest'
import type { ApiResponse } from '../types/world'


export class PlayerQuestApiError extends Error {
  constructor(
    public readonly status: number | null,
    message: string,
  ) {
    super(message)
    this.name = 'PlayerQuestApiError'
  }
}

export class PlayerQuestConflictError extends PlayerQuestApiError {
  constructor(message: string) {
    super(409, message)
    this.name = 'PlayerQuestConflictError'
  }
}

export const fetchPlayerQuest: PlayerQuestFetcher = async () => {
  try {
    const response = await api.get<ApiResponse<PlayerQuestData>>('/api/player')
    return response.data.data
  } catch (caught) {
    throw normalizePlayerQuestError(caught)
  }
}

export const travelPlayer: PlayerTraveller = async (locationId) => {
  try {
    const response = await api.post<ApiResponse<PlayerQuestData>>(
      '/api/player/travel',
      { target_location_id: locationId },
    )
    return response.data.data
  } catch (caught) {
    throw normalizePlayerQuestError(caught)
  }
}

export const interactWithMissingChildQuest: QuestInteractor = async (
  request: QuestInteractRequest,
) => {
  try {
    const response = await api.post<ApiResponse<PlayerQuestData>>(
      '/api/quests/missing-child/interact',
      request,
    )
    return response.data.data
  } catch (caught) {
    throw normalizePlayerQuestError(caught)
  }
}

function normalizePlayerQuestError(caught: unknown): PlayerQuestApiError {
  if (!axios.isAxiosError(caught)) {
    return new PlayerQuestApiError(null, 'Player quest request failed')
  }

  const status = caught.response?.status ?? null
  const responseMessage = caught.response?.data?.message
  const safeMessage = (
    (status === 404 || status === 409 || status === 503)
    && typeof responseMessage === 'string'
  )
    ? responseMessage
    : 'Player quest request failed'

  return status === 409
    ? new PlayerQuestConflictError(safeMessage)
    : new PlayerQuestApiError(status, safeMessage)
}
