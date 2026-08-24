import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import TownGameHost from '../../frontend/src/components/TownGameHost.vue'
import type {
  NpcVisualProjection,
  TownGameCallbacks,
  TownGameController,
  TownGameFactory,
} from '../../frontend/src/game/contracts'
import type { LocalPlayerProfileV1 } from '../../frontend/src/player/playerProfile'


const profile: LocalPlayerProfileV1 = {
  version: 1,
  displayName: '洛恩',
  adventurerClass: 'ranger',
  introCompleted: true,
}
const ryan: NpcVisualProjection = {
  id: 'ryan',
  name: 'Ryan',
  locationId: 'park',
  anchorName: 'location:park',
  offsetX: 0,
  offsetY: -24,
}
const shir: NpcVisualProjection = {
  id: 'shir',
  name: 'Shir',
  locationId: 'tavern',
  anchorName: 'location:tavern',
  offsetX: 24,
  offsetY: 0,
}

function fakeController(): TownGameController & {
  updateNpcs: ReturnType<typeof vi.fn>
  destroy: ReturnType<typeof vi.fn>
} {
  return {
    updateNpcs: vi.fn(),
    destroy: vi.fn(),
  }
}

describe('TownGameHost', () => {
  it('updates NPCs without rebuilding and forwards selection before cleanup', async () => {
    const controller = fakeController()
    let callbacks: TownGameCallbacks | undefined
    const factory = vi.fn<TownGameFactory>((parent, input, nextCallbacks) => {
      expect(parent).toBeInstanceOf(HTMLElement)
      expect(input).toEqual({ profile, npcs: [ryan] })
      callbacks = nextCallbacks
      return controller
    })
    const wrapper = mount(TownGameHost, {
      props: { profile, npcs: [ryan], factory },
    })
    await flushPromises()

    expect(factory).toHaveBeenCalledOnce()
    expect(wrapper.find('[role="status"]').exists()).toBe(false)

    await wrapper.setProps({ npcs: [shir] })
    expect(controller.updateNpcs).toHaveBeenCalledWith([shir])
    expect(factory).toHaveBeenCalledOnce()

    callbacks?.onNpcSelected('shir')
    expect(wrapper.emitted('npcSelected')).toEqual([['shir']])

    wrapper.unmount()
    expect(controller.destroy).toHaveBeenCalledOnce()
  })

  it('shows a load error and destroys the old game before retrying', async () => {
    const first = fakeController()
    const second = fakeController()
    let firstCallbacks: TownGameCallbacks | undefined
    const factory = vi.fn<TownGameFactory>((_parent, _input, callbacks) => {
      if (factory.mock.calls.length === 1) {
        firstCallbacks = callbacks
        return first
      }
      return second
    })
    const wrapper = mount(TownGameHost, {
      props: { profile, npcs: [ryan], factory },
    })
    await flushPromises()

    firstCallbacks?.onLoadFailed('地图资源加载失败，请重试。')
    await wrapper.vm.$nextTick()
    expect(wrapper.get('[role="alert"]').text()).toContain('地图资源加载失败')

    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(first.destroy).toHaveBeenCalledOnce()
    expect(factory).toHaveBeenCalledTimes(2)
    expect(first.destroy.mock.invocationCallOrder[0])
      .toBeLessThan(factory.mock.invocationCallOrder[1]!)
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)

    wrapper.unmount()
    expect(second.destroy).toHaveBeenCalledOnce()
  })
})
