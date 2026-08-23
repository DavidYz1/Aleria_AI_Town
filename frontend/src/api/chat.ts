import axios from 'axios'

import { api } from './client'
import type { ApiResponse } from '../types/world'
import type {
  ChatFetcher,
  NpcChatData,
  NpcChatRequest,
} from '../types/chat'


export class ChatApiError extends Error {
  constructor(
    public readonly status: number | null,
    message: string,
  ) {
    super(message)
    this.name = 'ChatApiError'
  }
}

export const sendNpcChat: ChatFetcher = async (
  npcId: string,
  request: NpcChatRequest,
): Promise<NpcChatData> => {
  try {
    const response = await api.post<ApiResponse<NpcChatData>>(
      `/api/npcs/${encodeURIComponent(npcId)}/chat`,
      request,
    )
    return response.data.data
  } catch (caught) {
    if (axios.isAxiosError(caught)) {
      const status = caught.response?.status ?? null
      const responseMessage = caught.response?.data?.message
      const message = (
        (status === 404 || status === 503)
        && typeof responseMessage === 'string'
      )
        ? responseMessage
        : 'Chat request failed'
      throw new ChatApiError(status, message)
    }
    throw new ChatApiError(null, 'Chat request failed')
  }
}
