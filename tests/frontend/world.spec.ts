import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

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
