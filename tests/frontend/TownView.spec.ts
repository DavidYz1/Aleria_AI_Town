import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { api } from '../../frontend/src/api/client'
import { useNpcChatStore } from '../../frontend/src/stores/npcChat'
import { useNpcDetailStore } from '../../frontend/src/stores/npcDetail'
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
  worldFixture,
} from './fixtures'

const teleportPlayer = vi.fn()
const TownGameHostStub = defineComponent({
  name: 'TownGameHost',
  props: {
    profile: { type: Object, required: true },
    playerLocationId: { type: String, default: null },
    npcs: { type: Array, required: true },
  },
  emits: ['npcSelected', 'playerLocationEntered'],
  setup(_props, { expose }) {
    expose({ teleportPlayer })
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
  const loadPlayerQuest = vi.spyOn(playerQuestStore, 'load').mockResolvedValue()
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

describe('TownView', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    teleportPlayer.mockReset()
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
    })
    expect(teleportPlayer).toHaveBeenCalledWith('castle')
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
    })
    expect(wrapper.get('.quest-panel').text()).toContain('灰烬战争旧封锁线')
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
    expect(wrapper.get('button').text()).toBe('重新加载')
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

  it('refreshes an open NPC detail only when the world tick changes', async () => {
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

  it('projects Backend NPC locations into the map without semantic travel', async () => {
    const { pinia, store } = createStore()
    store.data = worldFixture
    vi.spyOn(store, 'loadWorld').mockResolvedValue()
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
    })
    expect(playerQuestStore.data?.player.location_id).toBe('forest')
    expect(teleportPlayer).not.toHaveBeenCalled()
  })

  it('discards a stale walked entry after quick travel succeeds', async () => {
    const { pinia, store, playerQuestStore } = createStore()
    store.data = worldFixture
    vi.spyOn(store, 'loadWorld').mockResolvedValue()
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
})
