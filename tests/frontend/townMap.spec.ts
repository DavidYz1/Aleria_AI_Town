// @vitest-environment node

import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import { TOWN_LOCATION_ANCHORS } from '../../frontend/src/game/playerMapPosition'


interface MapObject {
  name: string
  x: number
  y: number
}

interface MapLayer {
  name: string
  objects?: MapObject[]
}

interface TownMap {
  orientation: string
  width: number
  height: number
  tilewidth: number
  tileheight: number
  layers: MapLayer[]
  tilesets: Array<{
    name: string
    image: string
  }>
}

const mapPath = fileURLToPath(new URL(
  '../../frontend/public/assets/phase2/maps/town.json',
  import.meta.url,
))

describe('phase 2 town map contract', () => {
  it('defines the required orthogonal tile layers and tileset', () => {
    const map = readMap()

    expect(map).toMatchObject({
      orientation: 'orthogonal',
      width: 48,
      height: 36,
      tilewidth: 32,
      tileheight: 32,
    })
    expect(map.layers.map(({ name }) => name)).toEqual([
      'ground',
      'decor-below',
      'collision',
      'decor-above',
      'objects',
    ])
    expect(map.tilesets).toEqual([
      expect.objectContaining({
        name: 'tiny-town-32',
        image: '../tiles/tiny-town-32.png',
      }),
    ])
  })

  it('keeps spawn and location anchors distinct and inside map bounds', () => {
    const map = readMap()
    const objects = map.layers.find(({ name }) => name === 'objects')?.objects
      ?? []
    const requiredNames = [
      'player_spawn',
      'location:tavern',
      'location:park',
      'location:castle',
      'location:forest',
      'location:fallback',
    ]

    expect(objects.map(({ name }) => name)).toEqual(requiredNames)
    for (const object of objects) {
      expect(object.x).toBeGreaterThanOrEqual(0)
      expect(object.x).toBeLessThan(map.width * map.tilewidth)
      expect(object.y).toBeGreaterThanOrEqual(0)
      expect(object.y).toBeLessThan(map.height * map.tileheight)
    }
    expect(new Set(objects.map(({ x, y }) => `${x},${y}`)).size)
      .toBe(objects.length)
  })

  it('keeps Vue nearest-location anchors aligned with the map objects', () => {
    const map = readMap()
    const objects = map.layers.find(({ name }) => name === 'objects')?.objects
      ?? []
    const actualAnchors = objects
      .filter(({ name }) => name.startsWith('location:') && name !== 'location:fallback')
      .map(({ name, x, y }) => ({ id: name.replace('location:', ''), x, y }))

    expect(actualAnchors).toEqual(TOWN_LOCATION_ANCHORS)
  })
})

function readMap(): TownMap {
  return JSON.parse(readFileSync(mapPath, 'utf8')) as TownMap
}
