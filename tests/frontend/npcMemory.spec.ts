import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '../../frontend/src/api/client'
import {
  fetchNpcMemoryExplanations,
  NpcNotFoundError,
} from '../../frontend/src/api/npc'
import { useNpcMemoryStore } from '../../frontend/src/stores/npcMemory'
import type { NpcMemoryExplanationsData } from '../../frontend/src/types/npc'
import { npcMemoryExplanationsFixture } from './fixtures'


function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

const shirMemoryFixture: NpcMemoryExplanationsData = {
  ...npcMemoryExplanationsFixture,
  npc_id: 'shir',
  retrieval_mode: 'lexical_fallback',
  fallback_used: true,
  memories: [],
}

describe('NPC memory explanation API adapter', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('encodes the NPC ID and unwraps the common API envelope', async () => {
    const get = vi.spyOn(api, 'get').mockResolvedValue({
      data: { success: true, data: npcMemoryExplanationsFixture, message: 'ok' },
    } as Awaited<ReturnType<typeof api.get>>)

    await expect(
      fetchNpcMemoryExplanations('ryan/name'),
    ).resolves.toEqual(npcMemoryExplanationsFixture)
    expect(get).toHaveBeenCalledWith('/api/npcs/ryan%2Fname/memory-explanations')
  })

  it('converts an Axios 404 into NpcNotFoundError', async () => {
    vi.spyOn(api, 'get').mockRejectedValue({
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
    })

    await expect(
      fetchNpcMemoryExplanations('missing-npc'),
    ).rejects.toBeInstanceOf(NpcNotFoundError)
  })

  it('preserves a non-404 request error such as the safe 503', async () => {
    const unavailable = new Error('service unavailable')
    vi.spyOn(api, 'get').mockRejectedValue(unavailable)

    await expect(fetchNpcMemoryExplanations('ryan')).rejects.toBe(unavailable)
  })
})

describe('NPC memory explanation store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('selects an NPC and stores the complete explanation response', async () => {
    const store = useNpcMemoryStore()

    await store.selectNpc('ryan', () => Promise.resolve(npcMemoryExplanationsFixture))

    expect(store.selectedNpcId).toBe('ryan')
    expect(store.data?.memories).toHaveLength(2)
    expect(store.data?.memories[0].source.label).toBe('亲历事件')
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
  })

  it('exposes loading until the selected NPC request resolves', async () => {
    const store = useNpcMemoryStore()
    const request = deferred<NpcMemoryExplanationsData>()

    const pending = store.selectNpc('ryan', () => request.promise)
    expect(store.loading).toBe(true)
    expect(store.data).toBeNull()

    request.resolve(npcMemoryExplanationsFixture)
    await pending

    expect(store.loading).toBe(false)
    expect(store.data?.npc_id).toBe('ryan')
  })

  it('maps a not-found error without clearing the selected identity', async () => {
    const store = useNpcMemoryStore()

    await store.selectNpc('missing-npc', () => Promise.reject(new NpcNotFoundError()))

    expect(store.selectedNpcId).toBe('missing-npc')
    expect(store.data).toBeNull()
    expect(store.error).toBe('没有找到这位居民。')
    expect(store.loading).toBe(false)
  })

  it('keeps an ordinary failure retryable without exposing the cause', async () => {
    const store = useNpcMemoryStore()
    await store.selectNpc('ryan', () => Promise.reject(new Error('embedding provider dsn')))
    const retryFetcher = vi.fn<(npcId: string) => Promise<NpcMemoryExplanationsData>>()
    retryFetcher.mockResolvedValue(npcMemoryExplanationsFixture)

    expect(store.error).toBe('相关记忆暂时无法读取，请稍后重试。')
    expect(store.error).not.toContain('dsn')

    await store.retry(retryFetcher)

    expect(retryFetcher).toHaveBeenCalledWith('ryan')
    expect(store.data?.npc_id).toBe('ryan')
    expect(store.error).toBeNull()
  })

  it('prevents a late response from replacing a newer selection', async () => {
    const store = useNpcMemoryStore()
    const ryanRequest = deferred<NpcMemoryExplanationsData>()
    const shirRequest = deferred<NpcMemoryExplanationsData>()
    const fetcher = vi.fn((npcId: string) => (
      npcId === 'ryan' ? ryanRequest.promise : shirRequest.promise
    ))

    const ryanPending = store.selectNpc('ryan', fetcher)
    const shirPending = store.selectNpc('shir', fetcher)
    shirRequest.resolve(shirMemoryFixture)
    await shirPending
    ryanRequest.resolve(npcMemoryExplanationsFixture)
    await ryanPending

    expect(store.selectedNpcId).toBe('shir')
    expect(store.data?.npc_id).toBe('shir')
    expect(store.data?.memories).toEqual([])
    expect(store.loading).toBe(false)
  })

  it('invalidates an in-flight response when the detail is closed', async () => {
    const store = useNpcMemoryStore()
    const request = deferred<NpcMemoryExplanationsData>()

    const pending = store.selectNpc('ryan', () => request.promise)
    store.close()
    request.resolve(npcMemoryExplanationsFixture)
    await pending

    expect(store.selectedNpcId).toBeNull()
    expect(store.data).toBeNull()
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
  })

  it('does not refresh when no NPC is selected', async () => {
    const store = useNpcMemoryStore()
    const fetcher = vi.fn<(npcId: string) => Promise<NpcMemoryExplanationsData>>()

    await store.refresh(fetcher)

    expect(fetcher).not.toHaveBeenCalled()
    expect(store.loading).toBe(false)
  })

  it('keeps the current explanations visible until a refresh replaces them', async () => {
    const store = useNpcMemoryStore()
    await store.selectNpc('ryan', () => Promise.resolve(npcMemoryExplanationsFixture))
    const request = deferred<NpcMemoryExplanationsData>()
    const degraded: NpcMemoryExplanationsData = {
      ...npcMemoryExplanationsFixture,
      retrieval_mode: 'lexical_fallback',
      fallback_used: true,
    }

    const pending = store.refresh(() => request.promise)
    expect(store.loading).toBe(true)
    expect(store.data?.fallback_used).toBe(false)

    request.resolve(degraded)
    await pending

    expect(store.loading).toBe(false)
    expect(store.data?.fallback_used).toBe(true)
    expect(store.data?.retrieval_mode).toBe('lexical_fallback')
  })
})
