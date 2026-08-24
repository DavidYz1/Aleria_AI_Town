import { describe, expect, it } from 'vitest'

import {
  LOCATION_ANCHORS,
  projectNpcs,
} from '../../frontend/src/game/npcProjection'


const npcs = [
  { id: 'ryan', name: 'Ryan', location_id: 'park' },
  { id: 'shir', name: 'Shir', location_id: 'tavern' },
  { id: 'grey', name: 'Grey', location_id: 'castle' },
]

describe('projectNpcs', () => {
  it('maps Backend location IDs to named map anchors', () => {
    expect(LOCATION_ANCHORS).toEqual({
      tavern: 'location:tavern',
      park: 'location:park',
      castle: 'location:castle',
      forest: 'location:forest',
    })

    expect(projectNpcs(npcs).map(({ id, anchorName }) => ({ id, anchorName })))
      .toEqual([
        { id: 'ryan', anchorName: 'location:park' },
        { id: 'shir', anchorName: 'location:tavern' },
        { id: 'grey', anchorName: 'location:castle' },
      ])
  })

  it('uses the fallback anchor for an unknown Backend location', () => {
    expect(projectNpcs([
      { id: 'future-npc', name: 'Future', location_id: 'harbor' },
    ])[0]).toMatchObject({
      locationId: 'harbor',
      anchorName: 'location:fallback',
    })
  })

  it('produces deterministic finite offsets without collapsing every NPC', () => {
    const first = projectNpcs(npcs)
    const second = projectNpcs(npcs)
    const allowed = [-24, 0, 24]

    expect(second).toEqual(first)
    for (const npc of first) {
      expect(allowed).toContain(npc.offsetX)
      expect(allowed).toContain(npc.offsetY)
    }
    expect(new Set(first.map((npc) => `${npc.offsetX},${npc.offsetY}`)).size)
      .toBeGreaterThan(1)
  })
})
