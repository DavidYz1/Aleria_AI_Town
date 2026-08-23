import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '../../frontend/src/api/client'
import { fetchNpcDetail, NpcNotFoundError } from '../../frontend/src/api/npc'
import { useNpcDetailStore } from '../../frontend/src/stores/npcDetail'
import type { NpcDetailData } from '../../frontend/src/types/npc'
import { npcDetailFixture } from './fixtures'


function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

const shirDetailFixture: NpcDetailData = {
  ...npcDetailFixture,
  profile: {
    id: 'shir',
    name: 'Shir',
    role: 'Assassin',
    personality: ['quiet', 'introverted', 'observant'],
  },
  state: {
    location_id: 'tavern',
    location_name: '星辰酒馆',
    current_action: 'eat',
    status: { energy: 72, mood: 65, social: 35 },
  },
  recent_actions: [],
}

describe('NPC detail API adapter', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('encodes the NPC ID and unwraps the common API envelope', async () => {
    const get = vi.spyOn(api, 'get').mockResolvedValue({
      data: { success: true, data: npcDetailFixture, message: 'ok' },
    } as Awaited<ReturnType<typeof api.get>>)

    await expect(fetchNpcDetail('ryan/name')).resolves.toEqual(npcDetailFixture)
    expect(get).toHaveBeenCalledWith('/api/npcs/ryan%2Fname')
  })

  it('converts an Axios 404 into NpcNotFoundError', async () => {
    const notFound = {
      name: 'AxiosError',
      message: 'not found',
      isAxiosError: true,
      config: {},
      response: {
        data: { success: false, data: null, message: 'NPC not found' },
        status: 404,
        statusText: 'Not Found',
        headers: {},
        config: {},
      },
      toJSON: () => ({}),
    }
    vi.spyOn(api, 'get').mockRejectedValue(notFound)

    await expect(fetchNpcDetail('missing-npc')).rejects.toBeInstanceOf(
      NpcNotFoundError,
    )
  })

  it('preserves non-404 request errors', async () => {
    const networkError = new Error('offline')
    vi.spyOn(api, 'get').mockRejectedValue(networkError)

    await expect(fetchNpcDetail('ryan')).rejects.toBe(networkError)
  })
})

describe('NPC detail store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('selects an NPC and stores the complete detail response', async () => {
    const store = useNpcDetailStore()

    await store.selectNpc('ryan', () => Promise.resolve(npcDetailFixture))

    expect(store.selectedNpcId).toBe('ryan')
    expect(store.data?.recent_actions[0].reason_code).toBe('knight_duty')
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
  })

  it('exposes loading until the selected NPC request resolves', async () => {
    const store = useNpcDetailStore()
    const request = deferred<NpcDetailData>()

    const pending = store.selectNpc('ryan', () => request.promise)
    expect(store.loading).toBe(true)
    expect(store.data).toBeNull()

    request.resolve(npcDetailFixture)
    await pending

    expect(store.loading).toBe(false)
    expect(store.data?.profile.id).toBe('ryan')
  })

  it('maps a not-found error without clearing the selected identity', async () => {
    const store = useNpcDetailStore()

    await store.selectNpc(
      'missing-npc',
      () => Promise.reject(new NpcNotFoundError()),
    )

    expect(store.selectedNpcId).toBe('missing-npc')
    expect(store.data).toBeNull()
    expect(store.error).toBe('没有找到这位居民。')
    expect(store.loading).toBe(false)
  })

  it('keeps an ordinary failure retryable for the selected NPC', async () => {
    const store = useNpcDetailStore()
    await store.selectNpc('ryan', () => Promise.reject(new Error('offline')))
    const retryFetcher = vi.fn<(npcId: string) => Promise<NpcDetailData>>()
    retryFetcher.mockResolvedValue(npcDetailFixture)

    expect(store.selectedNpcId).toBe('ryan')
    expect(store.error).toBe('居民详情加载失败，请稍后重试。')

    await store.retry(retryFetcher)

    expect(retryFetcher).toHaveBeenCalledWith('ryan')
    expect(store.data?.profile.id).toBe('ryan')
    expect(store.error).toBeNull()
  })

  it('prevents a late response from replacing a newer selection', async () => {
    const store = useNpcDetailStore()
    const ryanRequest = deferred<NpcDetailData>()
    const shirRequest = deferred<NpcDetailData>()
    const fetcher = vi.fn((npcId: string) => (
      npcId === 'ryan' ? ryanRequest.promise : shirRequest.promise
    ))

    const ryanPending = store.selectNpc('ryan', fetcher)
    const shirPending = store.selectNpc('shir', fetcher)
    shirRequest.resolve(shirDetailFixture)
    await shirPending
    ryanRequest.resolve(npcDetailFixture)
    await ryanPending

    expect(store.selectedNpcId).toBe('shir')
    expect(store.data?.profile.id).toBe('shir')
    expect(store.loading).toBe(false)
  })

  it('invalidates an in-flight response when the detail is closed', async () => {
    const store = useNpcDetailStore()
    const request = deferred<NpcDetailData>()

    const pending = store.selectNpc('ryan', () => request.promise)
    store.close()
    request.resolve(npcDetailFixture)
    await pending

    expect(store.selectedNpcId).toBeNull()
    expect(store.data).toBeNull()
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
  })

  it('does not refresh when no NPC is selected', async () => {
    const store = useNpcDetailStore()
    const fetcher = vi.fn<(npcId: string) => Promise<NpcDetailData>>()

    await store.refresh(fetcher)

    expect(fetcher).not.toHaveBeenCalled()
    expect(store.loading).toBe(false)
  })

  it('keeps current detail visible until refresh atomically replaces it', async () => {
    const store = useNpcDetailStore()
    await store.selectNpc('ryan', () => Promise.resolve(npcDetailFixture))
    const request = deferred<NpcDetailData>()
    const refreshedDetail: NpcDetailData = {
      ...npcDetailFixture,
      world_context: {
        ...npcDetailFixture.world_context,
        time: '10:00',
        tick: 2,
      },
    }

    const pending = store.refresh(() => request.promise)
    expect(store.loading).toBe(true)
    expect(store.data?.world_context.tick).toBe(1)

    request.resolve(refreshedDetail)
    await pending

    expect(store.loading).toBe(false)
    expect(store.data?.world_context.tick).toBe(2)
  })
})
