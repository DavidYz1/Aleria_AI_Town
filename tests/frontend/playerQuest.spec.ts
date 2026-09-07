import { createPinia, setActivePinia } from 'pinia'
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '../../frontend/src/api/client'
import { PlayerQuestConflictError } from '../../frontend/src/api/playerQuest'
import { usePlayerQuestStore } from '../../frontend/src/stores/playerQuest'
import type { PlayerQuestData } from '../../frontend/src/types/playerQuest'
import {
  acceptedPlayerQuestFixture,
  availablePlayerQuestFixture,
} from './fixtures'


function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

function atForest(): PlayerQuestData {
  return {
    ...acceptedPlayerQuestFixture,
    player: {
      ...acceptedPlayerQuestFixture.player,
      location_id: 'forest',
      location_name: '低语森林',
    },
  }
}

describe('player quest store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('loads authoritative state and clears a previous load error', async () => {
    const store = usePlayerQuestStore()

    await store.load(async () => {
      throw new Error('offline')
    })
    expect(store.data).toBeNull()
    expect(store.error).toBe('玩家任务加载失败，请稍后重试。')

    await store.retry(async () => availablePlayerQuestFixture)

    expect(store.data).toEqual(availablePlayerQuestFixture)
    expect(store.error).toBeNull()
    expect(store.loading).toBe(false)
  })

  it('refreshes the authoritative world before releasing a successful travel mutation', async () => {
    const store = usePlayerQuestStore()
    store.data = availablePlayerQuestFixture

    const reloadWorld = vi.fn(async () => true)
    const travelled = await store.travel('forest', 4, async (locationId, worldVersion) => {
      expect(locationId).toBe('forest')
      expect(worldVersion).toBe(4)
      expect(store.data).toEqual(availablePlayerQuestFixture)
      return atForest()
    }, reloadWorld)

    expect(store.data).toEqual(atForest())
    expect(travelled).toBe(true)
    expect(reloadWorld).toHaveBeenCalledTimes(1)
    expect(store.mutationError).toBeNull()
    expect(store.mutating).toBe(false)
  })

  it('uses the current quest version and supplied world version for an interaction', async () => {
    const store = usePlayerQuestStore()
    store.data = acceptedPlayerQuestFixture

    await store.interact('ask_grey', 4, async (request) => {
      expect(request).toEqual({
        interaction: 'ask_grey',
        expected_version: 1,
        expected_world_version: 4,
      })
      return {
        ...acceptedPlayerQuestFixture,
        quest: {
          ...acceptedPlayerQuestFixture.quest,
          status: 'briefed_by_grey',
          version: 2,
          objective: '前往低语森林，在灰烬战争旧封锁线附近寻找线索。',
          available_interactions: [],
        },
      }
    })

    expect(store.data?.quest.status).toBe('briefed_by_grey')
    expect(store.data?.quest.version).toBe(2)
  })

  it('ignores a second mutation while one is pending', async () => {
    const store = usePlayerQuestStore()
    const firstRequest = deferred<PlayerQuestData>()
    const traveller = vi.fn(() => firstRequest.promise)
    store.data = availablePlayerQuestFixture

    const first = store.travel('castle', 0, traveller)
    const second = store.travel('forest', 0, traveller)
    expect(await second).toBe(false)

    expect(traveller).toHaveBeenCalledTimes(1)
    expect(store.mutating).toBe(true)

    firstRequest.resolve(acceptedPlayerQuestFixture)
    await first
    expect(store.data).toEqual(acceptedPlayerQuestFixture)
  })

  it('preserves the last good state when a mutation fails', async () => {
    const store = usePlayerQuestStore()
    store.data = acceptedPlayerQuestFixture

    const travelled = await store.travel('forest', 1, async () => {
      throw new Error('transport details')
    })

    expect(travelled).toBe(false)
    expect(store.data).toEqual(acceptedPlayerQuestFixture)
    expect(store.mutationError).toBe('操作失败，当前玩家与任务状态未改变。')
  })

  it('keeps the mutation guard until conflict recovery refreshes both player and world state', async () => {
    const store = usePlayerQuestStore()
    store.data = availablePlayerQuestFixture
    const playerRefresh = deferred<Awaited<ReturnType<typeof api.get>>>()
    const worldRefresh = deferred<boolean>()
    vi.spyOn(api, 'get').mockReturnValue(playerRefresh.promise)
    const refreshWorld = vi.fn(() => worldRefresh.promise)

    const pending = store.interact('accept_quest', 0, async () => {
      throw new PlayerQuestConflictError('Quest state has changed')
    }, refreshWorld)

    await flushPromises()
    expect(store.mutating).toBe(true)

    playerRefresh.resolve({
      data: { success: true, data: acceptedPlayerQuestFixture, message: 'ok' },
    } as Awaited<ReturnType<typeof api.get>>)
    await flushPromises()

    expect(store.data).toEqual(acceptedPlayerQuestFixture)
    expect(store.mutating).toBe(true)

    worldRefresh.resolve(true)
    await pending

    expect(store.data).toEqual(acceptedPlayerQuestFixture)
    expect(store.mutationError).toBe('任务状态已更新，已刷新最新进度。')
    expect(store.mutating).toBe(false)
  })

  it('reports failed conflict recovery without claiming both states refreshed', async () => {
    const store = usePlayerQuestStore()
    store.data = availablePlayerQuestFixture
    vi.spyOn(api, 'get').mockResolvedValue({
      data: { success: true, data: acceptedPlayerQuestFixture, message: 'ok' },
    } as Awaited<ReturnType<typeof api.get>>)

    await store.interact(
      'accept_quest',
      0,
      async () => { throw new PlayerQuestConflictError('Quest state has changed') },
      async () => false,
    )

    expect(store.data).toEqual(acceptedPlayerQuestFixture)
    expect(store.mutationError).toBe('任务状态已更新，但刷新失败，请重试。')
    expect(store.mutating).toBe(false)
  })

  it('ignores conflict refresh results that arrive after restart', async () => {
    const store = usePlayerQuestStore()
    store.data = availablePlayerQuestFixture
    const playerRefresh = deferred<Awaited<ReturnType<typeof api.get>>>()
    const worldRefresh = deferred<boolean>()
    vi.spyOn(api, 'get').mockReturnValue(playerRefresh.promise)

    const pending = store.interact(
      'accept_quest',
      0,
      async () => { throw new PlayerQuestConflictError('Quest state has changed') },
      () => worldRefresh.promise,
    )
    await flushPromises()
    store.reset()
    playerRefresh.resolve({
      data: { success: true, data: acceptedPlayerQuestFixture, message: 'ok' },
    } as Awaited<ReturnType<typeof api.get>>)
    worldRefresh.resolve(true)
    await pending

    expect(store.data).toBeNull()
    expect(store.mutationError).toBeNull()
    expect(store.mutating).toBe(false)
  })

  it('does not let an older load response overwrite newer state', async () => {
    const store = usePlayerQuestStore()
    const oldRequest = deferred<PlayerQuestData>()

    const oldLoad = store.load(() => oldRequest.promise)
    await store.load(async () => acceptedPlayerQuestFixture)
    oldRequest.resolve(availablePlayerQuestFixture)
    await oldLoad

    expect(store.data).toEqual(acceptedPlayerQuestFixture)
    expect(store.loading).toBe(false)
  })

  it('clears state and ignores a player response from before restart', async () => {
    const store = usePlayerQuestStore()
    const request = deferred<PlayerQuestData>()
    const pending = store.load(() => request.promise)

    store.reset()
    request.resolve(acceptedPlayerQuestFixture)
    await pending

    expect(store.data).toBeNull()
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
    expect(store.mutating).toBe(false)
    expect(store.mutationError).toBeNull()
  })
})
