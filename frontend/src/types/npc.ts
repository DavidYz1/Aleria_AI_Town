import type { ActionId, NpcStatus } from './world'
import type { TargetKind } from './worldTick'


export type TimePhase = 'morning' | 'day' | 'evening' | 'night'

export interface NpcProfileDetail {
  id: string
  name: string
  role: string
  personality: string[]
}

export interface NpcStateDetail {
  location_id: string
  location_name: string
  current_action: ActionId
  status: NpcStatus
}

export interface NpcWorldContext {
  day: number
  time: string
  tick: number
  time_phase: TimePhase
}

export interface NpcRecentAction {
  id: number
  tick: number
  world_time: string
  action_type: ActionId
  target_kind: TargetKind | null
  target_id: string | null
  target_name: string | null
  reason_code: string
  reason_text: string
}

export interface NpcDetailData {
  profile: NpcProfileDetail
  state: NpcStateDetail
  world_context: NpcWorldContext
  recent_actions: NpcRecentAction[]
}
