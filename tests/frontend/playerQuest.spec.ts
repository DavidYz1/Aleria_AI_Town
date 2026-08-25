import { createPinia, setActivePinia } from 'pinia'
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

  it('atomically replaces state after travel succeeds', async () => {
    const store = usePlayerQuestStore()
    store.data = availablePlayerQuestFixture

    const travelled = await store.travel('forest', async (locationId) => {
      expect(locationId).toBe('forest')
      expect(store.data).toEqual(availablePlayerQuestFixture)
      return atForest()
    })

    expect(store.data).toEqual(atForest())
    expect(travelled).toBe(true)
    expect(store.mutationError).toBeNull()
    expect(store.mutating).toBe(false)
  })

  it('uses the current quest version for an interaction', async () => {
    const store = usePlayerQuestStore()
    store.data = acceptedPlayerQuestFixture

    await store.interact('ask_grey', async (request) => {
      expect(request).toEqual({
        interaction: 'ask_grey',
        expected_version: 1,
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

    const first = store.travel('castle', traveller)
    const second = store.travel('forest', traveller)
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

    const travelled = await store.travel('forest', async () => {
      throw new Error('transport details')
    })

    expect(travelled).toBe(false)
    expect(store.data).toEqual(acceptedPlayerQuestFixture)
    expect(store.mutationError).toBe('操作失败，当前玩家与任务状态未改变。')
  })

  it('reloads authoritative state and explains a quest conflict', async () => {
    const store = usePlayerQuestStore()
    store.data = availablePlayerQuestFixture
    vi.spyOn(api, 'get').mockResolvedValue({
      data: { success: true, data: acceptedPlayerQuestFixture, message: 'ok' },
    } as Awaited<ReturnType<typeof api.get>>)

    await store.interact('accept_quest', async () => {
      throw new PlayerQuestConflictError('Quest state has changed')
    })

    expect(store.data).toEqual(acceptedPlayerQuestFixture)
    expect(store.mutationError).toBe('任务状态已更新，已刷新最新进度。')
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
