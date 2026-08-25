import { describe, expect, it, vi } from 'vitest'

import { TownGameBridge } from '../../frontend/src/game/TownGameBridge'
import type {
  NpcVisualProjection,
  TownGameInput,
} from '../../frontend/src/game/contracts'


const initialNpc: NpcVisualProjection = {
  id: 'ryan',
  name: 'Ryan',
  locationId: 'park',
  anchorName: 'location:park',
  offsetX: 0,
  offsetY: -24,
}

function input(): TownGameInput {
  return {
    profile: {
      version: 1,
      displayName: '洛恩',
      adventurerClass: 'ranger',
      introCompleted: true,
    },
    playerLocationId: 'tavern',
    npcs: [{ ...initialNpc }],
  }
}

describe('TownGameBridge', () => {
  it('keeps a copied latest NPC snapshot and emits copied updates', () => {
    const source = input()
    const bridge = new TownGameBridge(source)
    const received: NpcVisualProjection[][] = []
    bridge.onNpcsUpdated((npcs) => received.push(npcs))
    source.npcs[0]!.name = 'mutated source'

    const update = [{
      ...initialNpc,
      locationId: 'castle',
      anchorName: 'location:castle',
    }]
    bridge.updateNpcs(update)
    update[0]!.name = 'mutated update'

    expect(received).toEqual([[
      expect.objectContaining({ name: 'Ryan', anchorName: 'location:castle' }),
    ]])
    expect(bridge.getInput().npcs).toEqual(received[0])
    expect(bridge.getInput().profile.displayName).toBe('洛恩')
  })

  it('stops notifying an NPC listener after unsubscribe', () => {
    const bridge = new TownGameBridge(input())
    const listener = vi.fn()
    const unsubscribe = bridge.onNpcsUpdated(listener)

    bridge.updateNpcs([])
    unsubscribe()
    bridge.updateNpcs([initialNpc])

    expect(listener).toHaveBeenCalledTimes(1)
    expect(listener).toHaveBeenCalledWith([])
  })

  it('clears NPC selection and load-failure listeners', () => {
    const bridge = new TownGameBridge(input())
    const selected = vi.fn()
    const loadFailed = vi.fn()
    bridge.onNpcSelected(selected)
    bridge.onLoadFailed(loadFailed)

    bridge.emitNpcSelected('ryan')
    bridge.emitLoadFailed('first failure')
    bridge.clear()
    bridge.emitNpcSelected('shir')
    bridge.emitLoadFailed('second failure')

    expect(selected).toHaveBeenCalledOnce()
    expect(selected).toHaveBeenCalledWith('ryan')
    expect(loadFailed).toHaveBeenCalledOnce()
    expect(loadFailed).toHaveBeenCalledWith('first failure')
  })

  it('bridges semantic location entry and player teleport commands', () => {
    const bridge = new TownGameBridge(input())
    const entered = vi.fn()
    const teleported = vi.fn()
    bridge.onPlayerLocationEntered(entered)
    bridge.onPlayerTeleport(teleported)

    bridge.emitPlayerLocationEntered('park')
    bridge.teleportPlayer('castle')

    expect(entered).toHaveBeenCalledOnce()
    expect(entered).toHaveBeenCalledWith('park')
    expect(teleported).toHaveBeenCalledOnce()
    expect(teleported).toHaveBeenCalledWith('castle')
    expect(bridge.getInput().playerLocationId).toBe('castle')

    bridge.clear()
    bridge.emitPlayerLocationEntered('forest')
    bridge.teleportPlayer('forest')
    expect(entered).toHaveBeenCalledOnce()
    expect(teleported).toHaveBeenCalledOnce()
  })
})
