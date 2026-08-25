import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useNpcDetailStore } from '../../frontend/src/stores/npcDetail'
import { useNpcChatStore } from '../../frontend/src/stores/npcChat'
import type { LocalPlayerProfileV1 } from '../../frontend/src/player/playerProfile'
import type {
  ChatFetcher,
  NpcChatData,
} from '../../frontend/src/types/chat'
import { chatResponseFixture } from './fixtures'


const profile: LocalPlayerProfileV1 = {
  version: 1,
  displayName: '洛恩',
  adventurerClass: 'ranger',
  introCompleted: true,
}


function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

function chatResult(
  npcId: string,
  conversationId: string,
  userId: number,
  content: string,
  options: { provider?: string, fallbackUsed?: boolean } = {},
): NpcChatData {
  return {
    conversation_id: conversationId,
    npc_id: npcId,
    turn: {
      user: { id: userId, role: 'user', content },
      assistant: {
        id: userId + 1,
        role: 'assistant',
        content: `${npcId} 回复 ${content}`,
        emotion: 'neutral',
      },
    },
    provider: options.provider ?? 'mock',
    fallback_used: options.fallbackUsed ?? false,
  }
}

describe('NPC Chat store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('appends only the authoritative pair returned by Backend', async () => {
    const store = useNpcChatStore()
    const fetcher = vi.fn<ChatFetcher>().mockResolvedValue(chatResponseFixture)
    store.setPendingMessage('ryan', '  你害怕史莱姆吗？  ')

    await store.send('ryan', profile, fetcher)

    expect(fetcher).toHaveBeenCalledWith('ryan', {
      conversation_id: null,
      message: '你害怕史莱姆吗？',
      player_profile: {
        display_name: '洛恩',
        adventurer_class: 'ranger',
      },
    })
    expect(store.sessionFor('ryan')).toMatchObject({
      conversationId: '5e547c21-a228-4e86-940d-a1bf5d65702f',
      messages: [
        chatResponseFixture.turn.user,
        chatResponseFixture.turn.assistant,
      ],
      sending: false,
      error: null,
      pendingMessage: '',
      provider: 'mock',
      fallbackUsed: false,
    })
  })

  it('keeps Ryan, Shir, and Grey sessions isolated', async () => {
    const store = useNpcChatStore()
    const results = {
      ryan: chatResult('ryan', '00000000-0000-0000-0000-000000000001', 1, 'Ryan hi'),
      shir: chatResult('shir', '00000000-0000-0000-0000-000000000002', 3, 'Shir hi'),
      grey: chatResult('grey', '00000000-0000-0000-0000-000000000003', 5, 'Grey hi'),
    }
    const fetcher: ChatFetcher = (npcId) => Promise.resolve(
      results[npcId as keyof typeof results],
    )

    for (const npcId of ['ryan', 'shir', 'grey']) {
      store.setPendingMessage(npcId, `${npcId} hi`)
    }
    await Promise.all([
      store.send('ryan', null, fetcher),
      store.send('shir', null, fetcher),
      store.send('grey', null, fetcher),
    ])

    expect(store.sessionFor('ryan').conversationId).toBe(results.ryan.conversation_id)
    expect(store.sessionFor('shir').conversationId).toBe(results.shir.conversation_id)
    expect(store.sessionFor('grey').conversationId).toBe(results.grey.conversation_id)
    expect(store.sessionFor('ryan').messages[1].content).toBe('ryan 回复 Ryan hi')
    expect(store.sessionFor('shir').messages[1].content).toBe('shir 回复 Shir hi')
    expect(store.sessionFor('grey').messages[1].content).toBe('grey 回复 Grey hi')
  })

  it('stores fallback metadata as a successful turn rather than an error', async () => {
    const store = useNpcChatStore()
    const result = chatResult(
      'grey',
      '00000000-0000-0000-0000-000000000004',
      1,
      '你好',
      { provider: 'mock', fallbackUsed: true },
    )
    store.setPendingMessage('grey', '你好')

    await store.send('grey', null, () => Promise.resolve(result))

    expect(store.sessionFor('grey')).toMatchObject({
      provider: 'mock',
      fallbackUsed: true,
      error: null,
      sending: false,
    })
  })

  it('does not send blank content or a duplicate in-flight request', async () => {
    const store = useNpcChatStore()
    const request = deferred<NpcChatData>()
    const fetcher = vi.fn<ChatFetcher>().mockReturnValue(request.promise)

    store.setPendingMessage('ryan', '   ')
    await store.send('ryan', null, fetcher)
    expect(fetcher).not.toHaveBeenCalled()

    store.setPendingMessage('ryan', '你好')
    const first = store.send('ryan', null, fetcher)
    const second = store.send('ryan', null, fetcher)
    expect(store.sessionFor('ryan').sending).toBe(true)
    expect(fetcher).toHaveBeenCalledTimes(1)

    request.resolve(chatResult(
      'ryan',
      '00000000-0000-0000-0000-000000000005',
      1,
      '你好',
    ))
    await Promise.all([first, second])
    expect(store.sessionFor('ryan').sending).toBe(false)
  })

  it('preserves a failed pending message and retries with the same conversation', async () => {
    const store = useNpcChatStore()
    const session = store.sessionFor('shir')
    session.conversationId = '00000000-0000-0000-0000-000000000006'
    store.setPendingMessage('shir', '继续聊')
    await store.send('shir', null, () => Promise.reject(new Error('offline')))

    expect(session.pendingMessage).toBe('继续聊')
    expect(session.error).toBe('消息发送失败，请稍后重试。')
    expect(session.sending).toBe(false)

    const retryFetcher = vi.fn<ChatFetcher>().mockResolvedValue(chatResult(
      'shir',
      session.conversationId,
      3,
      '继续聊',
    ))
    await store.retry('shir', profile, retryFetcher)

    expect(retryFetcher).toHaveBeenCalledWith('shir', {
      conversation_id: '00000000-0000-0000-0000-000000000006',
      message: '继续聊',
      player_profile: {
        display_name: '洛恩',
        adventurer_class: 'ranger',
      },
    })
    expect(session.error).toBeNull()
    expect(session.pendingMessage).toBe('')
  })

  it('ignores a stale response without clearing a newer error', async () => {
    const store = useNpcChatStore()
    const firstRequest = deferred<NpcChatData>()
    const secondRequest = deferred<NpcChatData>()
    const fetcher = vi.fn<ChatFetcher>()
      .mockReturnValueOnce(firstRequest.promise)
      .mockReturnValueOnce(secondRequest.promise)
    store.setPendingMessage('ryan', 'first')
    const first = store.send('ryan', null, fetcher)

    store.sessionFor('ryan').sending = false
    store.setPendingMessage('ryan', 'second')
    const second = store.send('ryan', null, fetcher)
    secondRequest.reject(new Error('new failure'))
    await second

    firstRequest.resolve(chatResult(
      'ryan',
      '00000000-0000-0000-0000-000000000007',
      1,
      'first',
    ))
    await first

    expect(store.sessionFor('ryan').messages).toEqual([])
    expect(store.sessionFor('ryan').pendingMessage).toBe('second')
    expect(store.sessionFor('ryan').error).toBe('消息发送失败，请稍后重试。')
  })

  it('clears every session and ignores responses from before a restart', async () => {
    const store = useNpcChatStore()
    const request = deferred<NpcChatData>()
    store.setPendingMessage('ryan', '重置前的消息')
    const pending = store.send('ryan', profile, () => request.promise)

    store.clearAll()
    request.resolve(chatResult(
      'ryan',
      '00000000-0000-0000-0000-000000000010',
      1,
      '重置前的消息',
    ))
    await pending

    expect(Object.keys(store.sessionsByNpc)).toEqual([])
  })

  it('stores a late Ryan response only in Ryan while Shir is active', async () => {
    const store = useNpcChatStore()
    const detailStore = useNpcDetailStore()
    const ryanRequest = deferred<NpcChatData>()
    detailStore.selectedNpcId = 'ryan'
    store.setPendingMessage('ryan', 'Ryan hi')
    const ryanPending = store.send('ryan', null, () => ryanRequest.promise)

    detailStore.selectedNpcId = 'shir'
    store.setPendingMessage('shir', 'Shir hi')
    await store.send('shir', null, () => Promise.resolve(chatResult(
      'shir',
      '00000000-0000-0000-0000-000000000008',
      1,
      'Shir hi',
    )))
    ryanRequest.resolve(chatResult(
      'ryan',
      '00000000-0000-0000-0000-000000000009',
      3,
      'Ryan hi',
    ))
    await ryanPending

    expect(detailStore.selectedNpcId).toBe('shir')
    expect(store.sessionFor('shir').messages[1].content).toBe('shir 回复 Shir hi')
    expect(store.sessionFor('ryan').messages[1].content).toBe('ryan 回复 Ryan hi')
  })

  it('omits player_profile entirely when no local profile is available', async () => {
    const store = useNpcChatStore()
    const fetcher = vi.fn<ChatFetcher>().mockResolvedValue(chatResponseFixture)
    store.setPendingMessage('ryan', '你好')

    await store.send('ryan', null, fetcher)

    expect(fetcher).toHaveBeenCalledWith('ryan', {
      conversation_id: null,
      message: '你好',
    })
    expect(fetcher.mock.calls[0]?.[1]).not.toHaveProperty('player_profile')
  })

  it('keeps chat sessions when NPC detail closes', () => {
    const store = useNpcChatStore()
    const detailStore = useNpcDetailStore()
    store.sessionFor('ryan').messages = [chatResponseFixture.turn.user]
    detailStore.selectedNpcId = 'ryan'

    detailStore.close()

    expect(detailStore.selectedNpcId).toBeNull()
    expect(store.sessionFor('ryan').messages).toEqual([
      chatResponseFixture.turn.user,
    ])
  })
})
