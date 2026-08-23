import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { WorldTickConflictError } from '../../frontend/src/api/world'
import { useWorldStore } from '../../frontend/src/stores/world'
import type { WorldData } from '../../frontend/src/types/world'
import type { WorldTickData } from '../../frontend/src/types/worldTick'
import { tickFixture, worldFixture } from './fixtures'

describe('world tick store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('sends current expected_tick and replaces world with authoritative response', async () => {
    const store = useWorldStore()
    store.data = worldFixture
    const advance = vi.fn<(expectedTick: number) => Promise<WorldTickData>>()
    advance.mockResolvedValue(tickFixture)

    await store.advanceTick(advance)

    expect(advance).toHaveBeenCalledWith(0)
    expect(store.data?.world).toEqual({
      id: 'aleria-town', name: '晨曦镇', day: 1, time: '09:00', tick: 1,
    })
    expect(store.lastTick?.actions).toHaveLength(3)
    expect(store.tickError).toBeNull()
  })

  it('keeps one in-flight request and disables duplicate advancement', async () => {
    const store = useWorldStore()
    store.data = worldFixture
    let resolve!: (value: WorldTickData) => void
    const request = new Promise<WorldTickData>((done) => { resolve = done })
    const advance = vi.fn(() => request)

    const first = store.advanceTick(advance)
    const second = store.advanceTick(advance)

    expect(store.advancing).toBe(true)
    expect(advance).toHaveBeenCalledTimes(1)
    resolve(tickFixture)
    await Promise.all([first, second])
    expect(store.advancing).toBe(false)
  })

  it('preserves the last valid world after an ordinary tick failure', async () => {
    const store = useWorldStore()
    store.data = worldFixture

    await store.advanceTick(() => Promise.reject(new Error('offline')))

    expect(store.data).toStrictEqual(worldFixture)
    expect(store.lastTick).toBeNull()
    expect(store.tickError).toBe('时间推进失败，当前世界状态未改变。')
  })

  it('reloads authoritative world after a stale-tick conflict', async () => {
    const store = useWorldStore()
    store.data = worldFixture
    store.lastTick = tickFixture
    const current: WorldData = {
      ...tickFixture.world,
      world: { ...tickFixture.world.world, time: '10:00', tick: 2 },
    }
    const reload = vi.fn().mockResolvedValue(current)

    await store.advanceTick(
      () => Promise.reject(new WorldTickConflictError()),
      reload,
    )

    expect(reload).toHaveBeenCalledTimes(1)
    expect(store.data?.world.tick).toBe(2)
    expect(store.lastTick).toBeNull()
    expect(store.tickError).toBe('世界已在其他请求中推进，已为你刷新最新状态。')
  })
})
