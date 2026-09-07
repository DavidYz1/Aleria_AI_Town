import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useWorldStore } from '../../frontend/src/stores/world'
import type { WorldData } from '../../frontend/src/types/world'
import { worldFixture } from './fixtures'


describe('world store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('exposes loading until the world request resolves', async () => {
    const store = useWorldStore()
    let resolve!: (value: WorldData) => void
    const request = new Promise<WorldData>((done) => {
      resolve = done
    })

    const pending = store.loadWorld(() => request)
    expect(store.loading).toBe(true)
    expect(store.error).toBeNull()

    resolve(worldFixture)
    await pending

    expect(store.loading).toBe(false)
    expect(store.data?.world.name).toBe('曦谷')
  })

  it('clears stale data and exposes a retryable error when loading fails', async () => {
    const store = useWorldStore()
    store.data = worldFixture

    await store.loadWorld(() => Promise.reject(new Error('network unavailable')))

    expect(store.data).toBeNull()
    expect(store.loading).toBe(false)
    expect(store.error).toBe('世界加载失败，请稍后重试。')
  })

  it('marks a response with missing locations as empty', async () => {
    const store = useWorldStore()
    const emptyWorld: WorldData = { ...worldFixture, locations: [] }

    await store.loadWorld(() => Promise.resolve(emptyWorld))

    expect(store.isEmpty).toBe(true)
  })

  it('refreshes authoritative data in the background without replacing the active game state', async () => {
    const store = useWorldStore()
    store.data = worldFixture
    let resolve!: (value: WorldData) => void
    const request = new Promise<WorldData>((done) => {
      resolve = done
    })

    const pending = store.refreshWorld(() => request)

    expect(store.loading).toBe(false)
    expect(store.canMutate).toBe(false)
    expect(store.data?.world.world_version).toBe(0)

    resolve({
      ...worldFixture,
      world: { ...worldFixture.world, world_version: 1, event_sequence: 1 },
    })

    await expect(pending).resolves.toBe(true)
    expect(store.loading).toBe(false)
    expect(store.canMutate).toBe(true)
    expect(store.data?.world.world_version).toBe(1)
  })

  it('blocks a new mutation after a background refresh fails with a known stale world', async () => {
    const store = useWorldStore()
    store.data = worldFixture
    const advance = vi.fn()

    await expect(store.refreshWorld(() => Promise.reject(new Error('offline')))).resolves.toBe(false)
    await store.advanceTick(advance)

    expect(store.data).toEqual(worldFixture)
    expect(store.canMutate).toBe(false)
    expect(advance).not.toHaveBeenCalled()
  })

  it('keeps a stale world locked until an in-place refresh retry succeeds', async () => {
    const store = useWorldStore()
    store.data = worldFixture
    let resolve!: (value: WorldData) => void
    const request = new Promise<WorldData>((done) => {
      resolve = done
    })

    await store.refreshWorld(() => Promise.reject(new Error('offline')))
    const pending = store.retryRefresh(() => request)

    expect(store.refreshError).toBe('世界刷新失败，请重试。')
    expect(store.refreshing).toBe(true)
    expect(store.canMutate).toBe(false)

    resolve({
      ...worldFixture,
      world: { ...worldFixture.world, world_version: 2, event_sequence: 2 },
    })
    await expect(pending).resolves.toBe(true)

    expect(store.refreshError).toBeNull()
    expect(store.refreshing).toBe(false)
    expect(store.canMutate).toBe(true)
    expect(store.data?.world.world_version).toBe(2)
  })

  it('clears state and ignores a world response from before restart', async () => {
    const store = useWorldStore()
    let resolve!: (value: WorldData) => void
    const request = new Promise<WorldData>((done) => {
      resolve = done
    })
    const pending = store.loadWorld(() => request)

    store.reset()
    resolve(worldFixture)
    await pending

    expect(store.data).toBeNull()
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
    expect(store.lastTick).toBeNull()
  })
})
