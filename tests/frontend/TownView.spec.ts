import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { api } from '../../frontend/src/api/client'
import { useNpcChatStore } from '../../frontend/src/stores/npcChat'
import { useNpcDetailStore } from '../../frontend/src/stores/npcDetail'
import { useNpcMemoryStore } from '../../frontend/src/stores/npcMemory'
import { usePlayerProfileStore } from '../../frontend/src/stores/playerProfile'
import { usePlayerQuestStore } from '../../frontend/src/stores/playerQuest'
import { useWorldStore } from '../../frontend/src/stores/world'
import type { NpcChatData } from '../../frontend/src/types/chat'
import TownView from '../../frontend/src/views/TownView.vue'
import {
  chatResponseFixture,
  acceptedPlayerQuestFixture,
  availablePlayerQuestFixture,
  npcDetailFixture,
  npcMemoryExplanationsFixture,
  worldFixture,
} from './fixtures'

const teleportPlayer = vi.fn()
const focusCanvas = vi.fn()
const TownGameHostStub = defineComponent({
  name: 'TownGameHost',
  props: {
    profile: { type: Object, required: true },
    playerLocationId: { type: String, default: null },
    npcs: { type: Array, required: true },
  },
  emits: ['npcSelected', 'playerLocationEntered'],
  setup(_props, { expose }) {
    expose({ teleportPlayer, focusCanvas })
    return {}
  },
  template: `
    <section class="town-game-host-stub" aria-label="测试地图">
      <button type="button" @click="$emit('npcSelected', 'ryan')">选择 Ryan</button>
    </section>
  `,
})

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise
  })
  return { promise, resolve }
}

function createStore() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const playerQuestStore = usePlayerQuestStore()
  usePlayerProfileStore().profile = {
    version: 1,
    displayName: '洛恩',
    adventurerClass: 'ranger',
    introCompleted: true,
  }
  playerQuestStore.data = availablePlayerQuestFixture
  const loadPlayerQuest = vi.spyOn(playerQuestStore, 'load').mockResolvedValue(true)
  return {
    pinia,
    store: useWorldStore(),
    playerQuestStore,
    loadPlayerQuest,
  }
}

function mountTownView(pinia: ReturnType<typeof createPinia>) {
  return mount(TownView, {
    global: {
      plugins: [pinia],
      stubs: { TownGameHost: TownGameHostStub },
    },
  })
}

const MEMORY_URL = '/api/npcs/ryan/memory-explanations'

function mockNpcGets(
  memory: () => Promise<unknown> = () => Promise.resolve(npcMemoryExplanationsFixture),
) {
  return vi.spyOn(api, 'get').mockImplementation((url) => {
    const envelope = (data: unknown) => ({
      data: { success: true, data, message: 'ok' },
    })
    if (url.endsWith('/memory-explanations')) {
      return memory().then(envelope) as ReturnType<typeof api.get>
    }
    if (url === '/api/player') {
      return Promise.resolve(envelope(availablePlayerQuestFixture)) as ReturnType<typeof api.get>
    }
    if (url === '/api/world') {
      return Promise.resolve(envelope(worldFixture)) as ReturnType<typeof api.get>
    }
    return Promise.resolve(envelope(npcDetailFixture)) as ReturnType<typeof api.get>
  })
}

function callsTo(get: ReturnType<typeof mockNpcGets>, url: string): number {
  return get.mock.calls.filter(([called]) => called === url).length
}

function openRyanDetail(wrapper: ReturnType<typeof mountTownView>) {
  const detailButtons = wrapper.findAll('button').filter(
    (button) => button.text() === '查看详情',
  )
  return detailButtons[0].trigger('click')
}

describe('TownView', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    teleportPlayer.mockReset()
    focusCanvas.mockReset()
  })

  it('loads World and PlayerQuest on mount through their real stores', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const get = vi.spyOn(api, 'get').mockImplementation((url) => {
      const data = url === '/api/world'
        ? worldFixture
        : availablePlayerQuestFixture
      return Promise.resolve({
        data: { success: true, data, message: 'ok' },
      }) as ReturnType<typeof api.get>
    })

    const wrapper = mountTownView(pinia)
    await flushPromises()

    expect(get).toHaveBeenCalledWith('/api/world')
    expect(get).toHaveBeenCalledWith('/api/player')
    expect(wrapper.get('.player-location-panel').text()).toContain('星辉酒馆')
    const tavern = wrapper.findAll('.location-card').find(
      (card) => card.get('h3').text() === '星辉酒馆',
    )
    expect(tavern?.classes()).toContain('is-current')
  })

  it('travels through the PlayerQuest store and updates the current card', async () => {
    const { pinia, store, playerQuestStore } = createStore()
    store.data = worldFixture
    vi.spyOn(store, 'loadWorld').mockResolvedValue()
    vi.spyOn(store, 'refreshWorld').mockResolvedValue(true)
    const travelled = {
      ...availablePlayerQuestFixture,
      player: {
        ...availablePlayerQuestFixture.player,
        location_id: 'castle',
        location_name: '晨曦城堡',
      },
      quest: {
        ...availablePlayerQuestFixture.quest,
        available_interactions: [],
      },
    }
    const post = vi.spyOn(api, 'post').mockResolvedValue({
      data: { success: true, data: travelled, message: 'ok' },
    } as Awaited<ReturnType<typeof api.post>>)

    const wrapper = mountTownView(pinia)
    await flushPromises()
    const castle = wrapper.findAll('.location-card').find(
      (card) => card.get('h3').text() === '晨曦城堡',
    )
    expect(castle).toBeDefined()
    await castle!.get('button').trigger('click')
    await flushPromises()

    expect(post).toHaveBeenCalledWith('/api/player/travel', {
      target_location_id: 'castle',
      expected_world_version: 0,
    })
    expect(teleportPlayer).toHaveBeenCalledWith('castle')
    expect(playerQuestStore.data?.player.location_id).toBe('castle')
    expect(castle!.classes()).toContain('is-current')
  })

  it('advances the visible quest using its current quest and world versions, then refreshes world', async () => {
    const { pinia, store, playerQuestStore } = createStore()
    store.data = worldFixture
    playerQuestStore.data = acceptedPlayerQuestFixture
    vi.spyOn(store, 'loadWorld').mockResolvedValue()
    const refreshWorld = vi.spyOn(store, 'refreshWorld').mockResolvedValue(true)
    const briefed = {
      ...acceptedPlayerQuestFixture,
      quest: {
        ...acceptedPlayerQuestFixture.quest,
        status: 'briefed_by_grey' as const,
        version: 2,
        objective: '前往低语森林，在灰烬战争旧封锁线附近寻找线索。',
        available_interactions: [],
      },
    }
    const post = vi.spyOn(api, 'post').mockResolvedValue({
      data: { success: true, data: briefed, message: 'ok' },
    } as Awaited<ReturnType<typeof api.post>>)

    const wrapper = mountTownView(pinia)
    await flushPromises()
    await wrapper.get('.quest-actions button').trigger('click')
    await flushPromises()

    expect(post).toHaveBeenCalledWith('/api/quests/missing-child/interact', {
      interaction: 'ask_grey',
      expected_version: 1,
      expected_world_version: 0,
    })
    expect(refreshWorld).toHaveBeenCalledTimes(1)
    expect(wrapper.get('.quest-panel').text()).toContain('灰烬战争旧封锁线')
  })

  it('retries a quest with the world version refreshed after a conflict', async () => {
    const { pinia, store, playerQuestStore } = createStore()
    store.data = worldFixture
    playerQuestStore.data = availablePlayerQuestFixture
    vi.spyOn(store, 'loadWorld').mockResolvedValue()
    const refreshedWorld = {
      ...worldFixture,
      world: { ...worldFixture.world, world_version: 1, event_sequence: 1 },
    }
    vi.spyOn(api, 'get').mockImplementation((url) => Promise.resolve({
      data: {
        success: true,
        data: url === '/api/player' ? availablePlayerQuestFixture : refreshedWorld,
        message: 'ok',
      },
    }) as ReturnType<typeof api.get>)
    const conflict = {
      isAxiosError: true,
      response: { status: 409, data: { message: 'Quest state has changed' } },
    }
    const post = vi.spyOn(api, 'post')
      .mockRejectedValueOnce(conflict)
      .mockResolvedValueOnce({
        data: { success: true, data: acceptedPlayerQuestFixture, message: 'ok' },
      } as Awaited<ReturnType<typeof api.post>>)

    const wrapper = mountTownView(pinia)
    await flushPromises()
    await wrapper.get('.quest-actions button').trigger('click')
    await flushPromises()

    expect(store.data?.world.world_version).toBe(1)
    await wrapper.get('.quest-actions button').trigger('click')
    await flushPromises()

    expect(post).toHaveBeenNthCalledWith(2, '/api/quests/missing-child/interact', {
      interaction: 'accept_quest',
      expected_version: 0,
      expected_world_version: 1,
    })
  })

  it('keeps World and NPC interactions available when PlayerQuest loading fails', async () => {
    const { pinia, store, playerQuestStore } = createStore()
    store.data = worldFixture
    playerQuestStore.data = null
    playerQuestStore.error = '玩家任务加载失败，请稍后重试。'
    vi.spyOn(store, 'loadWorld').mockResolvedValue()

    const wrapper = mountTownView(pinia)
    await flushPromises()

    expect(wrapper.get('.player-location-panel [role="alert"]').text()).toContain(
      '玩家任务加载失败',
    )
    expect(wrapper.findAll('.location-card')).toHaveLength(4)
    expect(wrapper.findAll('.npc-card')).toHaveLength(3)
  })

  it('renders the canonical town, locations, and NPCs from store state', async () => {
    const { pinia, store } = createStore()
    store.data = worldFixture
    vi.spyOn(store, 'loadWorld').mockResolvedValue()

    const wrapper = mountTownView(pinia)
    await flushPromises()

    expect(wrapper.get('h1').text()).toContain('曦谷')
    expect(wrapper.text()).toContain('Day 1 · 08:00')
    for (const text of [
      '星辉酒馆',
      '中央公园',
      '晨曦城堡',
      '低语森林',
      'Ryan',
      'Shir',
      'Grey',
    ]) {
      expect(wrapper.text()).toContain(text)
    }
  })

  it('announces loading state', async () => {
    const { pinia, store } = createStore()
    store.loading = true
    vi.spyOn(store, 'loadWorld').mockResolvedValue()

    const wrapper = mountTownView(pinia)
    await flushPromises()

    expect(wrapper.get('h1').text()).toContain('曦谷')
    expect(wrapper.get('[role="status"]').text()).toContain('正在读取曦谷…')
  })

  it('shows a retry action after loading fails', async () => {
    const { pinia, store } = createStore()
    store.error = '世界加载失败，请稍后重试。'
    vi.spyOn(store, 'loadWorld').mockResolvedValue()

    const wrapper = mountTownView(pinia)
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toContain(store.error)
    expect(wrapper.get('.error-panel button').text()).toBe('重新加载')
  })

  it('announces incomplete world data', async () => {
    const { pinia, store } = createStore()
    store.data = { ...worldFixture, locations: [] }
    vi.spyOn(store, 'loadWorld').mockResolvedValue()

    const wrapper = mountTownView(pinia)
    await flushPromises()

    expect(wrapper.get('[role="status"]').text()).toContain('世界数据尚未准备完成。')
  })

  it('opens and closes the selected NPC detail through the real stores', async () => {
    const { pinia, store } = createStore()
    store.data = worldFixture
    vi.spyOn(store, 'loadWorld').mockResolvedValue()
    vi.spyOn(api, 'get').mockResolvedValue({
      data: { success: true, data: npcDetailFixture, message: 'ok' },
    } as Awaited<ReturnType<typeof api.get>>)

    const wrapper = mountTownView(pinia)
    await flushPromises()

    const detailButtons = wrapper.findAll('button').filter(
      (button) => button.text() === '查看详情',
    )
    expect(detailButtons).toHaveLength(3)

    await detailButtons[0].trigger('click')
    await flushPromises()

    const detailStore = useNpcDetailStore()
    expect(detailStore.selectedNpcId).toBe('ryan')
    expect(detailStore.data?.profile.name).toBe('Ryan')
    expect(wrapper.get('.npc-detail-panel').text()).toContain('Ryan')

    await wrapper.get('button[aria-label="关闭居民详情"]').trigger('click')

    expect(detailStore.selectedNpcId).toBeNull()
    expect(wrapper.find('.npc-detail-panel').exists()).toBe(false)
  })

  it('opens NPC detail and an independent chat panel from one selection', async () => {
    const { pinia, store } = createStore()
    store.data = worldFixture
    vi.spyOn(store, 'loadWorld').mockResolvedValue()
    vi.spyOn(api, 'get').mockResolvedValue({
      data: { success: true, data: npcDetailFixture, message: 'ok' },
    } as Awaited<ReturnType<typeof api.get>>)

    const wrapper = mountTownView(pinia)
    await flushPromises()
    const detailButtons = wrapper.findAll('button').filter(
      (button) => button.text() === '查看详情',
    )
    await detailButtons[0].trigger('click')
    await flushPromises()

    expect(wrapper.get('.npc-detail-panel').text()).toContain('Ryan')
    expect(wrapper.get('.npc-chat-panel').text()).toContain('与 Ryan 对话')
    expect(wrapper.get('.npc-chat-panel').text()).toContain('还没有聊天记录')
  })

  it('sends through the real chat store and renders Backend messages', async () => {
    const { pinia, store } = createStore()
    usePlayerProfileStore().profile = {
      version: 1,
      displayName: '洛恩',
      adventurerClass: 'ranger',
      introCompleted: true,
    }
    store.data = worldFixture
    vi.spyOn(store, 'loadWorld').mockResolvedValue()
    vi.spyOn(api, 'get').mockResolvedValue({
      data: { success: true, data: npcDetailFixture, message: 'ok' },
    } as Awaited<ReturnType<typeof api.get>>)
    const post = vi.spyOn(api, 'post').mockResolvedValue({
      data: { success: true, data: chatResponseFixture, message: 'ok' },
    } as Awaited<ReturnType<typeof api.post>>)

    const wrapper = mountTownView(pinia)
    await flushPromises()
    const detailButtons = wrapper.findAll('button').filter(
      (button) => button.text() === '查看详情',
    )
    await detailButtons[0].trigger('click')
    await flushPromises()
    await wrapper.get('.npc-chat-panel textarea').setValue('你害怕史莱姆吗？')
    await wrapper.get('.npc-chat-panel form').trigger('submit')
    await flushPromises()

    const chat = wrapper.get('.npc-chat-panel')
    expect(chat.text()).toContain('你害怕史莱姆吗？')
    expect(chat.text()).toContain('害怕？当然不是')
    expect(chat.text()).toContain('Mock 模式')
    expect(post).toHaveBeenCalledWith('/api/npcs/ryan/chat', {
      conversation_id: null,
      message: '你害怕史莱姆吗？',
      player_profile: {
        display_name: '洛恩',
        adventurer_class: 'ranger',
      },
    }, { timeout: 60_000 })
  })

  it('keeps TownGameHost mounted while a successful travel waits for background world refresh', async () => {
    const { pinia, store } = createStore()
    store.data = worldFixture
    const refreshedWorld = deferred<Awaited<ReturnType<typeof api.get>>>()
    const travelled = {
      ...availablePlayerQuestFixture,
      player: { ...availablePlayerQuestFixture.player, location_id: 'castle', location_name: '晨曦城堡' },
    }
    vi.spyOn(api, 'post').mockResolvedValue({
      data: { success: true, data: travelled, message: 'ok' },
    } as Awaited<ReturnType<typeof api.post>>)
    vi.spyOn(api, 'get')
      .mockResolvedValueOnce({
        data: { success: true, data: worldFixture, message: 'ok' },
      } as Awaited<ReturnType<typeof api.get>>)
      .mockReturnValueOnce(refreshedWorld.promise)

    const wrapper = mountTownView(pinia)
    await flushPromises()
    const castle = wrapper.findAll('.location-card').find(
      (card) => card.get('h3').text() === '晨曦城堡',
    )
    void castle!.get('button').trigger('click')
    await flushPromises()

    expect(wrapper.findComponent(TownGameHostStub).exists()).toBe(true)
    expect(store.loading).toBe(false)

    refreshedWorld.resolve({
      data: {
        success: true,
        data: { ...worldFixture, world: { ...worldFixture.world, world_version: 1, event_sequence: 1 } },
        message: 'ok',
      },
    } as Awaited<ReturnType<typeof api.get>>)
    await flushPromises()

    expect(store.data?.world.world_version).toBe(1)
  })

  it('recovers a failed background refresh in place before allowing a new travel token', async () => {
    const { pinia, store } = createStore()
    store.data = worldFixture
    vi.spyOn(store, 'loadWorld').mockResolvedValue()
    await store.refreshWorld(() => Promise.reject(new Error('offline')))
    const retryResponse = deferred<Awaited<ReturnType<typeof api.get>>>()
    const worldAfterRetry = {
      ...worldFixture,
      world: { ...worldFixture.world, world_version: 2, event_sequence: 2 },
    }
    vi.spyOn(api, 'get')
      .mockReturnValueOnce(retryResponse.promise)
      .mockResolvedValueOnce({
        data: { success: true, data: worldAfterRetry, message: 'ok' },
      } as Awaited<ReturnType<typeof api.get>>)
    const travelled = {
      ...availablePlayerQuestFixture,
      player: { ...availablePlayerQuestFixture.player, location_id: 'castle', location_name: '晨曦城堡' },
    }
    const post = vi.spyOn(api, 'post').mockResolvedValue({
      data: { success: true, data: travelled, message: 'ok' },
    } as Awaited<ReturnType<typeof api.post>>)

    const wrapper = mountTownView(pinia)
    await flushPromises()
    expect(wrapper.findComponent(TownGameHostStub).exists()).toBe(true)
    expect(wrapper.get('.world-refresh-error').text()).toContain('世界刷新失败')

    void wrapper.get('.world-refresh-error button').trigger('click')
    await flushPromises()
    const castle = wrapper.findAll('.location-card').find(
      (card) => card.get('h3').text() === '晨曦城堡',
    )
    expect(wrapper.findComponent(TownGameHostStub).exists()).toBe(true)
    expect(wrapper.get('.world-refresh-error button').attributes('disabled')).toBeDefined()
    await castle!.get('button').trigger('click')
    expect(post).not.toHaveBeenCalled()

    retryResponse.resolve({
      data: { success: true, data: worldAfterRetry, message: 'ok' },
    } as Awaited<ReturnType<typeof api.get>>)
    await flushPromises()
    expect(wrapper.find('.world-refresh-error').exists()).toBe(false)
    expect(store.data?.world.world_version).toBe(2)

    await castle!.get('button').trigger('click')
    await flushPromises()
    expect(post).toHaveBeenCalledWith('/api/player/travel', {
      target_location_id: 'castle',
      expected_world_version: 2,
    })
  })

  it('restores each NPC chat after switching and closing detail', async () => {
    const { pinia, store } = createStore()
    const chatStore = useNpcChatStore()
    store.data = worldFixture
    chatStore.sessionFor('ryan').messages = [
      chatResponseFixture.turn.user,
      chatResponseFixture.turn.assistant,
    ]
    vi.spyOn(store, 'loadWorld').mockResolvedValue()
    vi.spyOn(api, 'get').mockResolvedValue({
      data: { success: true, data: npcDetailFixture, message: 'ok' },
    } as Awaited<ReturnType<typeof api.get>>)

    const wrapper = mountTownView(pinia)
    await flushPromises()
    const detailButtons = wrapper.findAll('button').filter(
      (button) => button.text() === '查看详情',
    )
    await detailButtons[0].trigger('click')
    await flushPromises()
    expect(wrapper.get('.npc-chat-panel').text()).toContain('害怕？当然不是')

    await detailButtons[1].trigger('click')
    await flushPromises()
    expect(wrapper.get('.npc-chat-panel').text()).toContain('与 Shir 对话')
    expect(wrapper.get('.npc-chat-panel').text()).toContain('还没有聊天记录')
    expect(wrapper.get('.npc-chat-panel').text()).not.toContain('害怕？当然不是')

    await detailButtons[0].trigger('click')
    await flushPromises()
    expect(wrapper.get('.npc-chat-panel').text()).toContain('害怕？当然不是')
    await wrapper.get('button[aria-label="关闭居民详情"]').trigger('click')
    expect(wrapper.find('.npc-chat-panel').exists()).toBe(false)

    await detailButtons[0].trigger('click')
    await flushPromises()
    expect(wrapper.get('.npc-chat-panel').text()).toContain('害怕？当然不是')
  })

  it('does not request or clear chat when World Tick changes', async () => {
    const { pinia, store, playerQuestStore } = createStore()
    const detailStore = useNpcDetailStore()
    const chatStore = useNpcChatStore()
    store.data = worldFixture
    detailStore.selectedNpcId = 'ryan'
    detailStore.data = npcDetailFixture
    chatStore.sessionFor('ryan').messages = [chatResponseFixture.turn.user]
    const playerQuestBefore = playerQuestStore.data
    vi.spyOn(store, 'loadWorld').mockResolvedValue()
    vi.spyOn(detailStore, 'refresh').mockResolvedValue()
    const post = vi.spyOn(api, 'post')

    const wrapper = mountTownView(pinia)
    await flushPromises()
    store.data = {
      ...worldFixture,
      world: { ...worldFixture.world, world_version: 1, clock_tick: 1, event_sequence: 3, time: '09:00' },
    }
    await flushPromises()

    expect(post).not.toHaveBeenCalled()
    expect(chatStore.sessionFor('ryan').messages).toEqual([
      chatResponseFixture.turn.user,
    ])
    expect(playerQuestStore.data).toEqual(playerQuestBefore)
    expect(wrapper.get('.npc-chat-panel').text()).toContain('你害怕史莱姆吗？')
  })

  it('does not render a late Ryan response in the active Shir panel', async () => {
    const { pinia, store } = createStore()
    const request = deferred<NpcChatData>()
    store.data = worldFixture
    vi.spyOn(store, 'loadWorld').mockResolvedValue()
    vi.spyOn(api, 'get').mockResolvedValue({
      data: { success: true, data: npcDetailFixture, message: 'ok' },
    } as Awaited<ReturnType<typeof api.get>>)
    vi.spyOn(api, 'post').mockReturnValue(request.promise.then((data) => ({
      data: { success: true, data, message: 'ok' },
    })) as ReturnType<typeof api.post>)

    const wrapper = mountTownView(pinia)
    await flushPromises()
    const detailButtons = wrapper.findAll('button').filter(
      (button) => button.text() === '查看详情',
    )
    await detailButtons[0].trigger('click')
    await flushPromises()
    await wrapper.get('.npc-chat-panel textarea').setValue('Ryan hi')
    await wrapper.get('.npc-chat-panel form').trigger('submit')
    await detailButtons[1].trigger('click')
    await flushPromises()

    request.resolve(chatResponseFixture)
    await flushPromises()

    expect(wrapper.get('.npc-chat-panel').text()).toContain('与 Shir 对话')
    expect(wrapper.get('.npc-chat-panel').text()).toContain('还没有聊天记录')
    expect(wrapper.get('.npc-chat-panel').text()).not.toContain('害怕？当然不是')
    expect(useNpcChatStore().sessionFor('ryan').messages).toHaveLength(2)
  })

  it('refreshes an open NPC detail when the authoritative world version changes without advancing the clock', async () => {
    const { pinia, store } = createStore()
    const detailStore = useNpcDetailStore()
    store.data = worldFixture
    detailStore.selectedNpcId = 'ryan'
    detailStore.data = npcDetailFixture
    vi.spyOn(store, 'loadWorld').mockResolvedValue()
    const refresh = vi.spyOn(detailStore, 'refresh').mockResolvedValue()

    mountTownView(pinia)
    await flushPromises()

    store.data = {
      ...worldFixture,
      world: { ...worldFixture.world, world_version: 1 },
    }
    await flushPromises()
    expect(refresh).toHaveBeenCalledTimes(1)

    store.data = {
      ...store.data,
      world: { ...store.data.world, name: '晨曦镇' },
    }
    await flushPromises()
    expect(refresh).toHaveBeenCalledTimes(1)

    detailStore.close()
    store.data = {
      ...store.data,
      world: { ...store.data.world, world_version: 2 },
    }
    await flushPromises()
    expect(refresh).toHaveBeenCalledTimes(1)
  })

  it('projects Backend NPC locations into the map without semantic travel', async () => {
    const { pinia, store } = createStore()
    store.data = worldFixture
    vi.spyOn(store, 'loadWorld').mockResolvedValue()
    vi.spyOn(store, 'refreshWorld').mockResolvedValue(true)
    const post = vi.spyOn(api, 'post')

    const wrapper = mountTownView(pinia)
    await flushPromises()

    const host = wrapper.getComponent(TownGameHostStub)
    expect(host.props('profile')).toMatchObject({
      displayName: '洛恩',
      adventurerClass: 'ranger',
    })
    expect(host.props('npcs')).toEqual([
      expect.objectContaining({ id: 'ryan', anchorName: 'location:park' }),
      expect.objectContaining({ id: 'shir', anchorName: 'location:tavern' }),
      expect.objectContaining({ id: 'grey', anchorName: 'location:castle' }),
    ])
    expect(post).not.toHaveBeenCalled()

    store.data = {
      ...worldFixture,
      npcs: worldFixture.npcs.map((npc) => npc.id === 'ryan'
        ? { ...npc, location_id: 'forest' }
        : npc),
    }
    await flushPromises()

    expect(host.props('npcs')).toEqual([
      expect.objectContaining({ id: 'ryan', anchorName: 'location:forest' }),
      expect.objectContaining({ id: 'shir', anchorName: 'location:tavern' }),
      expect.objectContaining({ id: 'grey', anchorName: 'location:castle' }),
    ])
    expect(post).not.toHaveBeenCalled()
  })

  it('persists a walked location entry without teleporting the player', async () => {
    const { pinia, store, playerQuestStore } = createStore()
    store.data = worldFixture
    vi.spyOn(store, 'loadWorld').mockResolvedValue()
    vi.spyOn(store, 'refreshWorld').mockResolvedValue(true)
    const travelled = {
      ...availablePlayerQuestFixture,
      player: {
        ...availablePlayerQuestFixture.player,
        location_id: 'castle',
        location_name: '晨曦城堡',
      },
      quest: {
        ...availablePlayerQuestFixture.quest,
        available_interactions: [],
      },
    }
    const post = vi.spyOn(api, 'post').mockResolvedValue({
      data: { success: true, data: travelled, message: 'ok' },
    } as Awaited<ReturnType<typeof api.post>>)
    const wrapper = mountTownView(pinia)
    await flushPromises()
    const host = wrapper.getComponent(TownGameHostStub)

    host.vm.$emit('playerLocationEntered', 'castle')
    await flushPromises()

    expect(post).toHaveBeenCalledWith('/api/player/travel', {
      target_location_id: 'castle',
      expected_world_version: 0,
    })
    expect(playerQuestStore.data?.player.location_id).toBe('castle')
    expect(wrapper.get('.player-location-panel').text()).toContain('晨曦城堡')
    expect(teleportPlayer).not.toHaveBeenCalled()
  })

  it('syncs the latest walked location after an existing mutation finishes', async () => {
    const { pinia, store, playerQuestStore } = createStore()
    store.data = worldFixture
    playerQuestStore.data = acceptedPlayerQuestFixture
    vi.spyOn(store, 'loadWorld').mockResolvedValue()
    vi.spyOn(store, 'refreshWorld').mockResolvedValue(true)
    const interactionResponse = deferred<Awaited<ReturnType<typeof api.post>>>()
    const briefed = {
      ...acceptedPlayerQuestFixture,
      quest: {
        ...acceptedPlayerQuestFixture.quest,
        status: 'briefed_by_grey' as const,
        version: 2,
        available_interactions: [],
      },
    }
    const enteredForest = {
      ...briefed,
      player: {
        ...briefed.player,
        location_id: 'forest',
        location_name: '低语森林',
      },
    }
    const post = vi.spyOn(api, 'post')
      .mockImplementationOnce(() => interactionResponse.promise)
      .mockResolvedValueOnce({
        data: { success: true, data: enteredForest, message: 'ok' },
      } as Awaited<ReturnType<typeof api.post>>)
    const wrapper = mountTownView(pinia)
    await flushPromises()

    await wrapper.get('.quest-actions button').trigger('click')
    wrapper.getComponent(TownGameHostStub).vm.$emit('playerLocationEntered', 'forest')
    await flushPromises()

    expect(post).toHaveBeenCalledTimes(1)
    interactionResponse.resolve({
      data: { success: true, data: briefed, message: 'ok' },
    } as Awaited<ReturnType<typeof api.post>>)
    await flushPromises()

    expect(post).toHaveBeenNthCalledWith(2, '/api/player/travel', {
      target_location_id: 'forest',
      expected_world_version: 0,
    })
    expect(playerQuestStore.data?.player.location_id).toBe('forest')
    expect(teleportPlayer).not.toHaveBeenCalled()
  })

  it('discards a stale walked entry after quick travel succeeds', async () => {
    const { pinia, store, playerQuestStore } = createStore()
    store.data = worldFixture
    vi.spyOn(store, 'loadWorld').mockResolvedValue()
    vi.spyOn(store, 'refreshWorld').mockResolvedValue(true)
    const quickTravelResponse = deferred<Awaited<ReturnType<typeof api.post>>>()
    const travelled = {
      ...availablePlayerQuestFixture,
      player: {
        ...availablePlayerQuestFixture.player,
        location_id: 'castle',
        location_name: '晨曦城堡',
      },
    }
    const post = vi.spyOn(api, 'post').mockImplementationOnce(
      () => quickTravelResponse.promise,
    )
    const wrapper = mountTownView(pinia)
    await flushPromises()
    const castle = wrapper.findAll('.location-card').find(
      (card) => card.get('h3').text() === '晨曦城堡',
    )

    void castle!.get('button').trigger('click')
    await flushPromises()
    wrapper.getComponent(TownGameHostStub).vm.$emit('playerLocationEntered', 'forest')
    quickTravelResponse.resolve({
      data: { success: true, data: travelled, message: 'ok' },
    } as Awaited<ReturnType<typeof api.post>>)
    await flushPromises()

    expect(post).toHaveBeenCalledTimes(1)
    expect(playerQuestStore.data?.player.location_id).toBe('castle')
    expect(teleportPlayer).toHaveBeenCalledWith('castle')
  })

  it('does not teleport after quick travel fails', async () => {
    const { pinia, store } = createStore()
    store.data = worldFixture
    vi.spyOn(store, 'loadWorld').mockResolvedValue()
    vi.spyOn(api, 'post').mockRejectedValue(new Error('offline'))
    const wrapper = mountTownView(pinia)
    await flushPromises()
    const castle = wrapper.findAll('.location-card').find(
      (card) => card.get('h3').text() === '晨曦城堡',
    )

    await castle!.get('button').trigger('click')
    await flushPromises()

    expect(teleportPlayer).not.toHaveBeenCalled()
    expect(wrapper.get('.player-location-panel').text()).toContain('星辉酒馆')
  })

  it('does not teleport unless Backend confirms the requested location', async () => {
    const { pinia, store } = createStore()
    store.data = worldFixture
    vi.spyOn(store, 'loadWorld').mockResolvedValue()
    vi.spyOn(store, 'refreshWorld').mockResolvedValue(true)
    vi.spyOn(api, 'post').mockResolvedValue({
      data: {
        success: true,
        data: availablePlayerQuestFixture,
        message: 'ok',
      },
    } as Awaited<ReturnType<typeof api.post>>)
    const wrapper = mountTownView(pinia)
    await flushPromises()
    const castle = wrapper.findAll('.location-card').find(
      (card) => card.get('h3').text() === '晨曦城堡',
    )

    await castle!.get('button').trigger('click')
    await flushPromises()

    expect(teleportPlayer).not.toHaveBeenCalled()
    expect(wrapper.get('.player-location-panel').text()).toContain('星辉酒馆')
  })

  it('opens the existing detail and chat panels from a map NPC selection', async () => {
    const { pinia, store } = createStore()
    store.data = worldFixture
    vi.spyOn(store, 'loadWorld').mockResolvedValue()
    vi.spyOn(api, 'get').mockResolvedValue({
      data: { success: true, data: npcDetailFixture, message: 'ok' },
    } as Awaited<ReturnType<typeof api.get>>)

    const wrapper = mountTownView(pinia)
    await flushPromises()
    wrapper.getComponent(TownGameHostStub).vm.$emit('npcSelected', 'ryan')
    await flushPromises()

    expect(useNpcDetailStore().selectedNpcId).toBe('ryan')
    expect(wrapper.get('.npc-detail-panel').text()).toContain('Ryan')
    expect(wrapper.get('.npc-chat-panel').text()).toContain('与 Ryan 对话')
  })

  it('places the map before World Tick while keeping DOM NPC fallbacks', async () => {
    const { pinia, store } = createStore()
    store.data = worldFixture
    vi.spyOn(store, 'loadWorld').mockResolvedValue()

    const wrapper = mountTownView(pinia)
    await flushPromises()

    const map = wrapper.get('.town-play-layout').element
    const tick = wrapper.get('.tick-panel').element
    expect(map.compareDocumentPosition(tick) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(wrapper.findAll('.npc-card')).toHaveLength(3)
    expect(wrapper.findAll('.location-card')).toHaveLength(4)
  })

  it('stacks the resident chat under the map and leaves the profile in the side column', async () => {
    const { pinia, store } = createStore()
    store.data = worldFixture
    vi.spyOn(store, 'loadWorld').mockResolvedValue()
    mockNpcGets()

    const wrapper = mountTownView(pinia)
    await flushPromises()
    wrapper.getComponent(TownGameHostStub).vm.$emit('npcSelected', 'ryan')
    await flushPromises()

    const mapColumn = wrapper.get('.town-game-host-column')
    expect(mapColumn.find('.npc-chat-panel').exists()).toBe(true)
    expect(mapColumn.find('.npc-detail-panel').exists()).toBe(false)
    expect(wrapper.get('.town-map-hud').find('.npc-detail-panel').exists()).toBe(true)

    const map = wrapper.get('.town-game-host-stub').element
    const chat = wrapper.get('.npc-chat-panel').element
    expect(map.compareDocumentPosition(chat) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('advances the world from the map shortcut and hands focus back to the canvas', async () => {
    const { pinia, store } = createStore()
    store.data = worldFixture
    vi.spyOn(store, 'loadWorld').mockResolvedValue()
    const advanceTick = vi.spyOn(store, 'advanceTick').mockResolvedValue()

    const wrapper = mountTownView(pinia)
    await flushPromises()
    await wrapper.get('[data-action="advance-world-from-map"]').trigger('click')

    expect(advanceTick).toHaveBeenCalledTimes(1)
    expect(focusCanvas).toHaveBeenCalledTimes(1)
  })

  it('disables both tick controls while one advance is in flight', async () => {
    const { pinia, store } = createStore()
    store.data = worldFixture
    vi.spyOn(store, 'loadWorld').mockResolvedValue()
    const tickResponse = deferred<Awaited<ReturnType<typeof api.post>>>()
    vi.spyOn(api, 'post').mockImplementation(
      (url) => url === '/api/world/tick'
        ? tickResponse.promise
        : Promise.reject(new Error(`unexpected mutation: ${url}`)),
    )

    const wrapper = mountTownView(pinia)
    await flushPromises()
    const shortcut = wrapper.get('[data-action="advance-world-from-map"]')
    await shortcut.trigger('click')
    await shortcut.trigger('click')
    await wrapper.get('.tick-panel button').trigger('click')

    expect(shortcut.attributes('disabled')).toBeDefined()
    expect(wrapper.get('.tick-panel button').attributes('disabled')).toBeDefined()
    expect(store.advancing).toBe(true)
  })

  it('cancels a full adventure restart before calling Backend', async () => {
    const { pinia, store } = createStore()
    store.data = worldFixture
    vi.spyOn(store, 'loadWorld').mockResolvedValue()
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    const post = vi.spyOn(api, 'post')
    const wrapper = mountTownView(pinia)
    await flushPromises()

    await wrapper.get('[data-action="restart-adventure"]').trigger('click')

    expect(post).not.toHaveBeenCalledWith('/api/demo/reset')
    expect(wrapper.emitted('restart')).toBeUndefined()
  })

  it('clears frontend world caches and requests Scene 0 after reset succeeds', async () => {
    const { pinia, store, playerQuestStore } = createStore()
    const detailStore = useNpcDetailStore()
    const memoryStore = useNpcMemoryStore()
    const chatStore = useNpcChatStore()
    store.data = worldFixture
    detailStore.selectedNpcId = 'ryan'
    detailStore.data = npcDetailFixture
    memoryStore.selectedNpcId = 'ryan'
    memoryStore.data = npcMemoryExplanationsFixture
    chatStore.sessionFor('ryan').messages.push(chatResponseFixture.turn.user)
    vi.spyOn(store, 'loadWorld').mockResolvedValue()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const post = vi.spyOn(api, 'post').mockResolvedValue({
      data: {
        success: true,
        data: {
          world_id: 'aleria-town',
          clock_tick: 0,
          player_location_id: 'tavern',
          quest_status: 'available',
        },
        message: 'Demo world reset',
      },
    } as Awaited<ReturnType<typeof api.post>>)
    const wrapper = mountTownView(pinia)
    await flushPromises()

    await wrapper.get('[data-action="restart-adventure"]').trigger('click')
    await flushPromises()

    expect(post).toHaveBeenCalledWith('/api/demo/reset')
    expect(wrapper.emitted('restart')).toEqual([[]])
    expect(store.data).toBeNull()
    expect(playerQuestStore.data).toBeNull()
    expect(detailStore.selectedNpcId).toBeNull()
    expect(memoryStore.selectedNpcId).toBeNull()
    expect(memoryStore.data).toBeNull()
    expect(Object.keys(chatStore.sessionsByNpc)).toEqual([])
  })

  it('blocks every game mutation while the reset request is pending', async () => {
    const { pinia, store } = createStore()
    const detailStore = useNpcDetailStore()
    const chatStore = useNpcChatStore()
    store.data = worldFixture
    detailStore.selectedNpcId = 'ryan'
    detailStore.data = npcDetailFixture
    chatStore.setPendingMessage('ryan', '重置期间不应发送')
    vi.spyOn(store, 'loadWorld').mockResolvedValue()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const resetResponse = deferred<Awaited<ReturnType<typeof api.post>>>()
    const post = vi.spyOn(api, 'post').mockImplementation(
      (url) => url === '/api/demo/reset'
        ? resetResponse.promise
        : Promise.reject(new Error(`unexpected mutation: ${url}`)),
    )
    const wrapper = mountTownView(pinia)
    await flushPromises()

    void wrapper.get('[data-action="restart-adventure"]').trigger('click')
    await wrapper.vm.$nextTick()
    wrapper.getComponent(TownGameHostStub).vm.$emit('playerLocationEntered', 'forest')
    await wrapper.get('.tick-panel button').trigger('click')
    await wrapper.get('.quest-actions button').trigger('click')
    const castle = wrapper.findAll('.location-card').find(
      (card) => card.get('h3').text() === '晨曦城堡',
    )
    await castle!.get('button').trigger('click')
    await wrapper.get('.chat-composer button').trigger('click')
    await flushPromises()

    expect(wrapper.get('.tick-panel button').attributes('disabled')).toBeDefined()
    expect(wrapper.get('.quest-actions button').attributes('disabled')).toBeDefined()
    expect(castle!.get('button').attributes('disabled')).toBeDefined()
    expect(wrapper.get('.chat-composer button').attributes('disabled')).toBeDefined()
    expect(post).toHaveBeenCalledTimes(1)
    expect(post).toHaveBeenCalledWith('/api/demo/reset')

    resetResponse.resolve({
      data: {
        success: true,
        data: {
          world_id: 'aleria-town',
          clock_tick: 0,
          player_location_id: 'tavern',
          quest_status: 'available',
        },
        message: 'Demo world reset',
      },
    } as Awaited<ReturnType<typeof api.post>>)
    await flushPromises()
  })

  it('opens the collapsed related memory section from one NPC selection', async () => {
    const { pinia, store } = createStore()
    store.data = worldFixture
    vi.spyOn(store, 'loadWorld').mockResolvedValue()
    const get = mockNpcGets()

    const wrapper = mountTownView(pinia)
    await flushPromises()
    await openRyanDetail(wrapper)
    await flushPromises()

    expect(get).toHaveBeenCalledWith('/api/npcs/ryan')
    expect(get).toHaveBeenCalledWith(MEMORY_URL)
    expect(useNpcMemoryStore().selectedNpcId).toBe('ryan')
    expect(useNpcMemoryStore().data?.memories).toHaveLength(2)

    const toggle = wrapper.get('.memory-explanations button[aria-controls]')
    expect(toggle.attributes('aria-expanded')).toBe('false')
    expect(wrapper.text()).not.toContain('在中央公园完成了一次骑士日常训练。')

    await toggle.trigger('click')

    expect(wrapper.get('.npc-detail-panel').text()).toContain('亲历事件')
    expect(wrapper.get('.npc-detail-panel').text()).toContain(
      '在中央公园完成了一次骑士日常训练。',
    )
  })

  it('keeps the NPC detail usable when only the memory read fails and retries just the memory', async () => {
    const { pinia, store } = createStore()
    store.data = worldFixture
    vi.spyOn(store, 'loadWorld').mockResolvedValue()
    let memoryFailures = 0
    const get = mockNpcGets(() => {
      memoryFailures += 1
      return memoryFailures === 1
        ? Promise.reject(new Error('cognition dsn unavailable'))
        : Promise.resolve(npcMemoryExplanationsFixture)
    })

    const wrapper = mountTownView(pinia)
    await flushPromises()
    await openRyanDetail(wrapper)
    await flushPromises()

    expect(useNpcDetailStore().error).toBeNull()
    expect(wrapper.get('.npc-detail-panel').text()).toContain('中央公园')
    expect(useNpcMemoryStore().error).toBe('相关记忆暂时无法读取，请稍后重试。')
    expect(wrapper.text()).not.toContain('cognition dsn unavailable')

    await wrapper.get('.memory-explanations button[aria-controls]').trigger('click')
    await wrapper.get('.memory-explanations [role="alert"] button').trigger('click')
    await flushPromises()

    expect(callsTo(get, MEMORY_URL)).toBe(2)
    expect(callsTo(get, '/api/npcs/ryan')).toBe(1)
    expect(useNpcMemoryStore().error).toBeNull()
    expect(wrapper.get('.memory-explanations').text()).toContain('亲历事件')
  })

  it('refreshes the selected NPC memory when the authoritative world version changes', async () => {
    const { pinia, store } = createStore()
    const detailStore = useNpcDetailStore()
    const memoryStore = useNpcMemoryStore()
    store.data = worldFixture
    detailStore.selectedNpcId = 'ryan'
    detailStore.data = npcDetailFixture
    memoryStore.selectedNpcId = 'ryan'
    memoryStore.data = npcMemoryExplanationsFixture
    vi.spyOn(store, 'loadWorld').mockResolvedValue()
    vi.spyOn(detailStore, 'refresh').mockResolvedValue()
    const refreshMemory = vi.spyOn(memoryStore, 'refresh').mockResolvedValue()

    mountTownView(pinia)
    await flushPromises()

    store.data = {
      ...worldFixture,
      world: { ...worldFixture.world, world_version: 1, clock_tick: 1 },
    }
    await flushPromises()
    expect(refreshMemory).toHaveBeenCalledTimes(1)

    detailStore.close()
    memoryStore.close()
    store.data = {
      ...store.data,
      world: { ...store.data.world, world_version: 2 },
    }
    await flushPromises()
    expect(refreshMemory).toHaveBeenCalledTimes(1)
  })

  it('refreshes the memory after a successful chat turn with the selected NPC', async () => {
    const { pinia, store } = createStore()
    store.data = worldFixture
    vi.spyOn(store, 'loadWorld').mockResolvedValue()
    const get = mockNpcGets()
    vi.spyOn(api, 'post').mockResolvedValue({
      data: { success: true, data: chatResponseFixture, message: 'ok' },
    } as Awaited<ReturnType<typeof api.post>>)

    const wrapper = mountTownView(pinia)
    await flushPromises()
    await openRyanDetail(wrapper)
    await flushPromises()
    expect(callsTo(get, MEMORY_URL)).toBe(1)

    await wrapper.get('.npc-chat-panel textarea').setValue('你害怕史莱姆吗？')
    await wrapper.get('.npc-chat-panel form').trigger('submit')
    await flushPromises()

    expect(callsTo(get, MEMORY_URL)).toBe(2)
    expect(callsTo(get, '/api/npcs/ryan')).toBe(1)
  })

  it('clears the memory store together with the detail when the panel is closed', async () => {
    const { pinia, store } = createStore()
    store.data = worldFixture
    vi.spyOn(store, 'loadWorld').mockResolvedValue()
    mockNpcGets()

    const wrapper = mountTownView(pinia)
    await flushPromises()
    await openRyanDetail(wrapper)
    await flushPromises()
    expect(useNpcMemoryStore().data).not.toBeNull()

    await wrapper.get('button[aria-label="关闭居民详情"]').trigger('click')

    expect(useNpcDetailStore().selectedNpcId).toBeNull()
    expect(useNpcMemoryStore().selectedNpcId).toBeNull()
    expect(useNpcMemoryStore().data).toBeNull()
    expect(wrapper.find('.memory-explanations').exists()).toBe(false)
  })

  it('stays in town and explains when Backend reset fails', async () => {
    const { pinia, store } = createStore()
    store.data = worldFixture
    vi.spyOn(store, 'loadWorld').mockResolvedValue()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    vi.spyOn(api, 'post').mockRejectedValue(new Error('offline'))
    const wrapper = mountTownView(pinia)
    await flushPromises()

    await wrapper.get('[data-action="restart-adventure"]').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('restart')).toBeUndefined()
    expect(wrapper.get('.demo-reset-error').text()).toContain(
      '重新开始失败，当前世界没有改变',
    )
  })
})
