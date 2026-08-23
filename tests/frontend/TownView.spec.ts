import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { api } from '../../frontend/src/api/client'
import { useNpcChatStore } from '../../frontend/src/stores/npcChat'
import { useNpcDetailStore } from '../../frontend/src/stores/npcDetail'
import { useWorldStore } from '../../frontend/src/stores/world'
import type { NpcChatData } from '../../frontend/src/types/chat'
import TownView from '../../frontend/src/views/TownView.vue'
import {
  chatResponseFixture,
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
  return { pinia, store: useWorldStore() }
}

describe('TownView', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the canonical town, locations, and NPCs from store state', async () => {
    const { pinia, store } = createStore()
    store.data = worldFixture
    vi.spyOn(store, 'loadWorld').mockResolvedValue()

    const wrapper = mount(TownView, { global: { plugins: [pinia] } })
    await flushPromises()

    expect(wrapper.get('h1').text()).toContain('晨曦镇')
    expect(wrapper.text()).toContain('Day 1 · 08:00')
    for (const text of ['星辰酒馆', '中央公园', 'Ryan', 'Shir', 'Grey']) {
      expect(wrapper.text()).toContain(text)
    }
  })

  it('announces loading state', async () => {
    const { pinia, store } = createStore()
    store.loading = true
    vi.spyOn(store, 'loadWorld').mockResolvedValue()

    const wrapper = mount(TownView, { global: { plugins: [pinia] } })
    await flushPromises()

    expect(wrapper.get('[role="status"]').text()).toContain('正在读取晨曦镇…')
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
    const { pinia, store } = createStore()
    const detailStore = useNpcDetailStore()
    const chatStore = useNpcChatStore()
    store.data = worldFixture
    detailStore.selectedNpcId = 'ryan'
    detailStore.data = npcDetailFixture
    chatStore.sessionFor('ryan').messages = [chatResponseFixture.turn.user]
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
