import axios from 'axios'

import { api } from './client'
import type { NpcDetailData, NpcMemoryExplanationsData } from '../types/npc'
import type { ApiResponse } from '../types/world'


export class NpcNotFoundError extends Error {
  constructor() {
    super('NPC not found')
    this.name = 'NpcNotFoundError'
  }
}

export async function fetchNpcDetail(npcId: string): Promise<NpcDetailData> {
  try {
    const response = await api.get<ApiResponse<NpcDetailData>>(
      `/api/npcs/${encodeURIComponent(npcId)}`,
    )
    return response.data.data
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      throw new NpcNotFoundError()
    }
    throw error
  }
}

export async function fetchNpcMemoryExplanations(
  npcId: string,
): Promise<NpcMemoryExplanationsData> {
  try {
    const response = await api.get<ApiResponse<NpcMemoryExplanationsData>>(
      `/api/npcs/${encodeURIComponent(npcId)}/memory-explanations`,
    )
    return response.data.data
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      throw new NpcNotFoundError()
    }
    throw error
  }
}
