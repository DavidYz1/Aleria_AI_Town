import type { ActionId, WorldData } from './world'

export type TargetKind = 'location' | 'npc'

export interface WorldActionInfo {
  id: number
  tick: number
  actor_id: string
  action_type: ActionId
  target_kind: TargetKind | null
  target_id: string | null
  reason: string
  status: 'recorded'
  world_time: string
}

export interface WorldEventInfo {
  id: number
  tick: number
  event_type: 'npc_action'
  actor_id: string
  action_id: number
  description: string
  world_time: string
}

export interface WorldTickData {
  world: WorldData
  actions: WorldActionInfo[]
  events: WorldEventInfo[]
}
