import type { ActionId, WorldData } from './world'

export type TargetKind = 'location' | 'npc'

export interface WorldActionInfo {
  id: number
  clock_tick: number
  actor_id: string
  action_type: ActionId
  target_kind: TargetKind | null
  target_id: string | null
  reason: string
  status: 'executed'
  run_id: string
  proposal_id: number
  world_version: number
  world_time: string
}

export interface WorldEventInfo {
  id: number
  run_id: string | null
  world_version: number
  clock_tick: number
  event_sequence: number
  event_type: string
  actor_id: string | null
  action_id: number | null
  source_event_id: number | null
  description: string
  world_time: string
  payload: Record<string, unknown>
  visibility: string
  secrecy: string
  causation_id: string | null
  correlation_id: string
  created_at: string
}

export interface AgentRunSummary {
  id: string
  mode: 'deterministic'
  trigger_type: 'world_advance'
  status: 'completed'
  base_world_version: number
  resulting_world_version: number
  base_clock_tick: number
  resulting_clock_tick: number
}

export interface WorldTickData {
  run: AgentRunSummary
  world: WorldData
  actions: WorldActionInfo[]
  events: WorldEventInfo[]
}
