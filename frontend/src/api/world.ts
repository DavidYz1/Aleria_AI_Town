import axios from 'axios'

import { api } from './client'
import type { ApiResponse, WorldData } from '../types/world'
import type { WorldTickData } from '../types/worldTick'

/**
 * Advancing the world plans every NPC, and live planning is a real model call:
 * measured 12-19s each, serially, so one tick runs 30-50s. The 5s client
 * default would abort a request the server goes on to complete — the world
 * advances and the player is told it failed. Only this one call needs the
 * longer ceiling; everything else keeps the snappy default.
 */
const WORLD_TICK_TIMEOUT_MS = 90_000

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
    const response = await api.post<ApiResponse<WorldTickData>>(
      '/api/world/tick',
      { expected_world_version: expectedWorldVersion },
      { timeout: WORLD_TICK_TIMEOUT_MS },
    )
    return response.data.data
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 409) {
      throw new WorldTickConflictError()
    }
    throw error
  }
}
