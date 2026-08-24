import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import App from '../../frontend/src/App.vue'
import {
  PLAYER_PROFILE_STORAGE_KEY,
} from '../../frontend/src/player/playerProfile'
import { usePlayerProfileStore } from '../../frontend/src/stores/playerProfile'
import TownView from '../../frontend/src/views/TownView.vue'

function mountApp() {
  const pinia = createPinia()
  setActivePinia(pinia)

  return mount(App, {
    global: {
      plugins: [pinia],
      stubs: {
        TownView: true,
      },
    },
  })
}

function mountAppWithTownLandmark() {
  const pinia = createPinia()
  setActivePinia(pinia)

  return mount(App, {
    global: {
      plugins: [pinia],
      stubs: {
        TownView: { template: '<main class="town-shell"></main>' },
      },
    },
  })
}

describe('adventurer onboarding flow', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('moves a new adventurer from boot through story and persists completion', async () => {
    const wrapper = mountApp()

    expect(wrapper.find('[data-scene="boot"]').exists()).toBe(true)

    await wrapper.get('[data-action="continue"]').trigger('click')
    expect(wrapper.find('[data-scene="create"]').exists()).toBe(true)

    await wrapper.get('input[name="displayName"]').setValue('洛恩')
    await wrapper.get('[data-class="ranger"]').trigger('click')
    await wrapper.get('form').trigger('submit')
    expect(wrapper.get('[data-scene="story"]').text()).toContain('洛恩')

    await wrapper.get('[data-action="skip-story"]').trigger('click')
    expect(wrapper.findComponent(TownView).exists()).toBe(true)
    expect(JSON.parse(localStorage.getItem(PLAYER_PROFILE_STORAGE_KEY)!)).toMatchObject({
      displayName: '洛恩',
      adventurerClass: 'ranger',
      introCompleted: true,
    })
  })

  it('keeps boot as the first scene and continues completed profiles to town', async () => {
    localStorage.setItem(PLAYER_PROFILE_STORAGE_KEY, JSON.stringify({
      version: 1,
      displayName: '洛恩',
      adventurerClass: 'ranger',
      introCompleted: true,
    }))
    const wrapper = mountApp()

    expect(wrapper.find('[data-scene="boot"]').exists()).toBe(true)

    await wrapper.get('[data-action="continue"]').trigger('click')

    expect(wrapper.findComponent(TownView).exists()).toBe(true)
  })

  it('does not nest the town landmark inside another main landmark', async () => {
    localStorage.setItem(PLAYER_PROFILE_STORAGE_KEY, JSON.stringify({
      version: 1,
      displayName: '洛恩',
      adventurerClass: 'ranger',
      introCompleted: true,
    }))
    const wrapper = mountAppWithTownLandmark()

    await wrapper.get('[data-action="continue"]').trigger('click')

    expect(wrapper.findAll('main')).toHaveLength(1)
  })

  it('does not render an empty storage-warning status when storage is available', async () => {
    const wrapper = mountApp()

    await wrapper.get('[data-action="continue"]').trigger('click')

    expect(wrapper.find('.storage-warning').exists()).toBe(false)
  })

  it('renders a storage warning before the character-creation scene', async () => {
    const wrapper = mountApp()

    await wrapper.get('[data-action="continue"]').trigger('click')
    usePlayerProfileStore().storageWarning = '当前浏览器无法保存角色，本次选择仅在此会话有效。'
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.storage-warning + [data-scene="create"]').exists()).toBe(true)
  })
})
