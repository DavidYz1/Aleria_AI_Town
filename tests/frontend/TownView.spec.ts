import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { api } from '../../frontend/src/api/client'
import { useNpcChatStore } from '../../frontend/src/stores/npcChat'
import { useNpcDetailStore } from '../../frontend/src/stores/npcDetail'
import { usePlayerQuestStore } from '../../frontend/src/stores/playerQuest'
import { useWorldStore } from '../../frontend/src/stores/world'
import type { NpcChatData } from '../../frontend/src/types/chat'
import TownView from '../../frontend/src/views/TownView.vue'
import {
  chatResponseFixture,
  acceptedPlayerQuestFixture,
  availablePlayerQuestFixture,
  npcDetailFixture,
  worldFixture,
} from './fixtures'

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
  playerQuestStore.data = availablePlayerQuestFixture
  const loadPlayerQuest = vi.spyOn(playerQuestStore, 'load').mockResolvedValue()
  return {
    pinia,
    store: useWorldStore(),
    playerQuestStore,
    loadPlayerQuest,
  }
}

describe('TownView', () => {
  afterEach(() => {
    vi.restoreAllMocks()
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

    const wrapper = mount(TownView, { global: { plugins: [pinia] } })
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

    const wrapper = mount(TownView, { global: { plugins: [pinia] } })
    await flushPromises()
    const castle = wrapper.findAll('.location-card').find(
      (card) => card.get('h3').text() === '晨曦城堡',
    )
    expect(castle).toBeDefined()
    await castle!.get('button').trigger('click')
    await flushPromises()

    expect(post).toHaveBeenCalledWith('/api/player/travel', {
      target_location_id: 'castle',
    })
    expect(playerQuestStore.data?.player.location_id).toBe('castle')
    expect(castle!.classes()).toContain('is-current')
  })

  it('advances the visible quest using its current Backend version', async () => {
    const { pinia, store, playerQuestStore } = createStore()
    store.data = worldFixture
    playerQuestStore.data = acceptedPlayerQuestFixture
    vi.spyOn(store, 'loadWorld').mockResolvedValue()
    const briefed = {
      ...acceptedPlayerQuestFixture,
      quest: {
        ...acceptedPlayerQuestFixture.quest,
        status: 'briefed_by_grey' as const,
        version: 2,
        objective: '前往低语森林寻找线索。',
        available_interactions: [],
      },
    }
    const post = vi.spyOn(api, 'post').mockResolvedValue({
      data: { success: true, data: briefed, message: 'ok' },
    } as Awaited<ReturnType<typeof api.post>>)

    const wrapper = mount(TownView, { global: { plugins: [pinia] } })
    await flushPromises()
    await wrapper.get('.quest-actions button').trigger('click')
    await flushPromises()

    expect(post).toHaveBeenCalledWith('/api/quests/missing-child/interact', {
      interaction: 'ask_grey',
      expected_version: 1,
    })
    expect(wrapper.get('.quest-panel').text()).toContain('前往低语森林寻找线索。')
  })

  it('keeps World and NPC interactions available when PlayerQuest loading fails', async () => {
    const { pinia, store, playerQuestStore } = createStore()
    store.data = worldFixture
    playerQuestStore.data = null
    playerQuestStore.error = '玩家任务加载失败，请稍后重试。'
    vi.spyOn(store, 'loadWorld').mockResolvedValue()

    const wrapper = mount(TownView, { global: { plugins: [pinia] } })
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

    const wrapper = mount(TownView, { global: { plugins: [pinia] } })
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

    const wrapper = mount(TownView, { global: { plugins: [pinia] } })
    await flushPromises()

    expect(wrapper.get('h1').text()).toContain('曦谷')
    expect(wrapper.get('[role="status"]').text()).toContain('正在读取曦谷…')
  })

  it('shows a retry action after loading fails', async () => {
    const { pinia, store } = createStore()
    store.error = '世界加载失败，请稍后重试。'
    vi.spyOn(store, 'loadWorld').mockResolvedValue()

    const wrapper = mount(TownView, { global: { plugins: [pinia] } })
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toContain(store.error)
    expect(wrapper.get('button').text()).toBe('重新加载')
  })

  it('announces incomplete world data', async () => {
    const { pinia, store } = createStore()
    store.data = { ...worldFixture, locations: [] }
    vi.spyOn(store, 'loadWorld').mockResolvedValue()

    const wrapper = mount(TownView, { global: { plugins: [pinia] } })
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

    const wrapper = mount(TownView, { global: { plugins: [pinia] } })
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

    const wrapper = mount(TownView, { global: { plugins: [pinia] } })
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
    store.data = worldFixture
    vi.spyOn(store, 'loadWorld').mockResolvedValue()
    vi.spyOn(api, 'get').mockResolvedValue({
      data: { success: true, data: npcDetailFixture, message: 'ok' },
    } as Awaited<ReturnType<typeof api.get>>)
    vi.spyOn(api, 'post').mockResolvedValue({
      data: { success: true, data: chatResponseFixture, message: 'ok' },
    } as Awaited<ReturnType<typeof api.post>>)

    const wrapper = mount(TownView, { global: { plugins: [pinia] } })
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

    const wrapper = mount(TownView, { global: { plugins: [pinia] } })
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

    const wrapper = mount(TownView, { global: { plugins: [pinia] } })
    await flushPromises()
    store.data = {
      ...worldFixture,
      world: { ...worldFixture.world, tick: 1, time: '09:00' },
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

    const wrapper = mount(TownView, { global: { plugins: [pinia] } })
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

  it('refreshes an open NPC detail only when the world tick changes', async () => {
    const { pinia, store } = createStore()
    const detailStore = useNpcDetailStore()
    store.data = worldFixture
    detailStore.selectedNpcId = 'ryan'
    detailStore.data = npcDetailFixture
    vi.spyOn(store, 'loadWorld').mockResolvedValue()
    const refresh = vi.spyOn(detailStore, 'refresh').mockResolvedValue()

    mount(TownView, { global: { plugins: [pinia] } })
    await flushPromises()

    store.data = {
      ...worldFixture,
      world: { ...worldFixture.world, tick: 1, time: '09:00' },
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
      world: { ...store.data.world, tick: 2, time: '10:00' },
    }
    await flushPromises()
    expect(refresh).toHaveBeenCalledTimes(1)
  })
})
