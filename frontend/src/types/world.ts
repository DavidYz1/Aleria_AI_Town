export interface ApiResponse<T> {
  success: boolean
  data: T
  message: string
}

export interface WorldInfo {
  id: string
  name: string
  day: number
  time: string
  tick: number
}

export interface LocationInfo {
  id: string
  name: string
  description: string
}

export interface NpcStatus {
  energy: number
  mood: number
  social: number
}

export type ActionId = 'move' | 'rest' | 'work' | 'eat' | 'social'

export interface NpcInfo {
  id: string
  name: string
  role: string
  personality: string[]
  location_id: string
  current_action: ActionId
  status: NpcStatus
}

export interface WorldData {
  world: WorldInfo
  locations: LocationInfo[]
  npcs: NpcInfo[]
}
