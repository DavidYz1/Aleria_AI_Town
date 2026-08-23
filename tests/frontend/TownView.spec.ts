import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { api } from '../../frontend/src/api/client'
import { useNpcDetailStore } from '../../frontend/src/stores/npcDetail'
import { useWorldStore } from '../../frontend/src/stores/world'
import TownView from '../../frontend/src/views/TownView.vue'
import { npcDetailFixture, worldFixture } from './fixtures'

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
