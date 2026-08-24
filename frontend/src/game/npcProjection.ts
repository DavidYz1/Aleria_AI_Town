import type { NpcVisualProjection } from './contracts'


export const LOCATION_ANCHORS = {
  tavern: 'location:tavern',
  park: 'location:park',
  castle: 'location:castle',
  forest: 'location:forest',
} as const

const FALLBACK_ANCHOR = 'location:fallback'
const OFFSET_GRID = [-24, 0, 24] as const

interface ProjectableNpc {
  id: string
  name: string
  location_id: string
}

export function projectNpcs(
  npcs: readonly ProjectableNpc[],
): NpcVisualProjection[] {
  return npcs.map((npc) => {
    const offsetIndex = stableHash(npc.id) % 9
    return {
      id: npc.id,
      name: npc.name,
      locationId: npc.location_id,
      anchorName: anchorForLocation(npc.location_id),
      offsetX: OFFSET_GRID[offsetIndex % 3],
      offsetY: OFFSET_GRID[Math.floor(offsetIndex / 3)],
    }
  })
}

function anchorForLocation(locationId: string): string {
  return LOCATION_ANCHORS[locationId as keyof typeof LOCATION_ANCHORS]
    ?? FALLBACK_ANCHOR
}

function stableHash(value: string): number {
  let hash = 2_166_136_261
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index)
    hash = Math.imul(hash, 16_777_619)
  }
  return hash >>> 0
}
