import { api } from './client'
import type { ApiResponse } from '../types/world'


export interface DemoResetData {
  world_id: string
  world_tick: number
  player_location_id: string
  quest_status: string
}

export class DemoResetApiError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'DemoResetApiError'
  }
}

export async function resetDemo(): Promise<DemoResetData> {
  try {
    const response = await api.post<ApiResponse<DemoResetData>>('/api/demo/reset')
    return response.data.data
  } catch {
    throw new DemoResetApiError('Demo reset failed')
  }
}
