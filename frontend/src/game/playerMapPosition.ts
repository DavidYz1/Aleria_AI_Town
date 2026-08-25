import type { PlayerMapPosition } from './contracts'


export const TOWN_LOCATION_ANCHORS = [
  { id: 'tavern', x: 416, y: 704 },
  { id: 'park', x: 768, y: 544 },
  { id: 'castle', x: 1152, y: 288 },
  { id: 'forest', x: 1280, y: 864 },
] as const
type TownLocationAnchor = typeof TOWN_LOCATION_ANCHORS[number]
const LOCATION_ENTER_RADIUS = 96

export function resolveEnteredPlayerLocationId(
  position: PlayerMapPosition,
): string | null {
  const entered = TOWN_LOCATION_ANCHORS.find(
    (anchor) => squaredDistance(position, anchor) <= LOCATION_ENTER_RADIUS ** 2,
  )
  return entered?.id ?? null
}

function squaredDistance(
  position: PlayerMapPosition,
  anchor: { x: number, y: number },
): number {
  return (position.x - anchor.x) ** 2 + (position.y - anchor.y) ** 2
}
