import axios from 'axios'

import { api } from './client'
import type { ApiResponse, WorldData } from '../types/world'
import type { WorldTickData } from '../types/worldTick'

export class WorldTickConflictError extends Error {
  constructor() {
    super('world tick conflict; refresh and retry')
    this.name = 'WorldTickConflictError'
  }
}

export async function fetchWorld(): Promise<WorldData> {
  const response = await api.get<ApiResponse<WorldData>>('/api/world')
  return response.data.data
}

export async function advanceWorldTick(expectedWorldVersion: number): Promise<WorldTickData> {
  try {
    const response = await api.post<ApiResponse<WorldTickData>>('/api/world/tick', {
      expected_world_version: expectedWorldVersion,
    })
    return response.data.data
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 409) {
      throw new WorldTickConflictError()
    }
    throw error
  }
}
