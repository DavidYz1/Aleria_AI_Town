import type { LocalPlayerProfileV1 } from '../player/playerProfile'


export interface NpcVisualProjection {
  id: string
  name: string
  locationId: string
  anchorName: string
  offsetX: number
  offsetY: number
}

export interface TownGameInput {
  profile: LocalPlayerProfileV1
  npcs: NpcVisualProjection[]
}

export interface TownGameController {
  updateNpcs(npcs: NpcVisualProjection[]): void
  destroy(): void
}

export interface TownGameCallbacks {
  onNpcSelected(npcId: string): void
  onLoadFailed(message: string): void
}

export type TownGameFactory = (
  parent: HTMLElement,
  input: TownGameInput,
  callbacks: TownGameCallbacks,
) => TownGameController | Promise<TownGameController>
