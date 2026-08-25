import type { LocalPlayerProfileV1 } from '../player/playerProfile'


export interface NpcVisualProjection {
  id: string
  name: string
  locationId: string
  anchorName: string
  offsetX: number
  offsetY: number
}

export interface PlayerMapPosition {
  x: number
  y: number
}

export interface TownGameInput {
  profile: LocalPlayerProfileV1
  playerLocationId: string | null
  npcs: NpcVisualProjection[]
}

export interface TownGameController {
  updateNpcs(npcs: NpcVisualProjection[]): void
  teleportPlayer(locationId: string): void
  destroy(): void
}

export interface TownGameCallbacks {
  onNpcSelected(npcId: string): void
  onPlayerLocationEntered(locationId: string): void
  onLoadFailed(message: string): void
}

export type TownGameFactory = (
  parent: HTMLElement,
  input: TownGameInput,
  callbacks: TownGameCallbacks,
) => TownGameController | Promise<TownGameController>
