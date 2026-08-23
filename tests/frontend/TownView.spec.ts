import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { useWorldStore } from '../../frontend/src/stores/world'
import TownView from '../../frontend/src/views/TownView.vue'
import { worldFixture } from './fixtures'

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
})
