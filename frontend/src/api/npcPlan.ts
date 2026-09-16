import axios from 'axios'

import { api } from './client'
import { NpcNotFoundError } from './npc'
import type { ApiResponse } from '../types/world'


/** Mirrors `backend/app/schemas/plan.py`. */
export type PlanStatus = 'active' | 'completed' | 'abandoned'

export interface PlanStepInfo {
  action_type: string
  target_kind: string | null
  target_id: string | null
  intent: string
}

/** 一条本次规划引用过、且允许公开的记忆。不可公开的不会出现在这里。 */
export interface PlanEvidenceItem {
  id: string
  type: string
  label: string
  summary: string
}

export interface PlanInfo {
  id: string
  goal: string
  goal_reason: string
  thought: string
  steps: PlanStepInfo[]
  current_step_index: number
  status: PlanStatus
  created_clock_tick: number
  provider: string
  model: string
  latency_ms: number | null
  tokens_used: number | null
  evidence: PlanEvidenceItem[]
}

export interface NpcPlanData {
  current: PlanInfo | null
  recent: PlanInfo[]
}

export async function fetchNpcPlan(npcId: string): Promise<NpcPlanData> {
  try {
    const response = await api.get<ApiResponse<NpcPlanData>>(
      `/api/npcs/${encodeURIComponent(npcId)}/plan`,
    )
    return response.data.data
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      throw new NpcNotFoundError()
    }
    throw error
  }
}
