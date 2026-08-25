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
  teleportPlayer: ReturnType<typeof vi.fn>
  destroy: ReturnType<typeof vi.fn>
} {
  return {
    updateNpcs: vi.fn(),
    teleportPlayer: vi.fn(),
    destroy: vi.fn(),
  }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((nextResolve) => {
    resolve = nextResolve
  })
  return { promise, resolve }
}

describe('TownGameHost', () => {
  it('updates NPCs without rebuilding and forwards selection before cleanup', async () => {
    const controller = fakeController()
    let callbacks: TownGameCallbacks | undefined
    const factory = vi.fn<TownGameFactory>((parent, input, nextCallbacks) => {
      expect(parent).toBeInstanceOf(HTMLElement)
      expect(input).toEqual({ profile, playerLocationId: 'tavern', npcs: [ryan] })
      callbacks = nextCallbacks
      return controller
    })
    const wrapper = mount(TownGameHost, {
      props: { profile, playerLocationId: 'tavern', npcs: [ryan], factory },
    })
    await flushPromises()

    expect(factory).toHaveBeenCalledOnce()
    expect(Object.keys(factory.mock.calls[0]![1]).sort()).toEqual([
      'npcs',
      'playerLocationId',
      'profile',
    ])
    expect(Object.keys(factory.mock.calls[0]![2]).sort()).toEqual([
      'onLoadFailed',
      'onNpcSelected',
      'onPlayerLocationEntered',
    ])
    expect(wrapper.find('[role="status"]').exists()).toBe(false)

    await wrapper.setProps({ npcs: [shir] })
    expect(controller.updateNpcs).toHaveBeenCalledWith([shir])
    expect(factory).toHaveBeenCalledOnce()

    callbacks?.onNpcSelected('shir')
    expect(wrapper.emitted('npcSelected')).toEqual([['shir']])

    callbacks?.onPlayerLocationEntered('park')
    expect(wrapper.emitted('playerLocationEntered')).toEqual([['park']])

    const host = wrapper.vm as unknown as {
      teleportPlayer(locationId: string): void
    }
    host.teleportPlayer('castle')
    expect(controller.teleportPlayer).toHaveBeenCalledWith('castle')

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
      props: { profile, playerLocationId: 'tavern', npcs: [ryan], factory },
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

  it('replays the latest NPC projection when props change during async startup', async () => {
    const controller = fakeController()
    const ready = deferred<TownGameController>()
    const factory = vi.fn<TownGameFactory>(() => ready.promise)
    const wrapper = mount(TownGameHost, {
      props: { profile, playerLocationId: 'tavern', npcs: [ryan], factory },
    })

    expect(factory).toHaveBeenCalledOnce()
    await wrapper.setProps({ npcs: [shir] })
    ready.resolve(controller)
    await flushPromises()

    expect(controller.updateNpcs).toHaveBeenCalledOnce()
    expect(controller.updateNpcs).toHaveBeenCalledWith([shir])
    expect(factory).toHaveBeenCalledOnce()

    wrapper.unmount()
  })

  it('aligns the player once when Backend location arrives after map startup', async () => {
    const controller = fakeController()
    const factory = vi.fn<TownGameFactory>(() => controller)
    const wrapper = mount(TownGameHost, {
      props: { profile, playerLocationId: null, npcs: [ryan], factory },
    })
    await flushPromises()

    await wrapper.setProps({ playerLocationId: 'tavern' })
    expect(controller.teleportPlayer).toHaveBeenCalledOnce()
    expect(controller.teleportPlayer).toHaveBeenCalledWith('tavern')

    await wrapper.setProps({ playerLocationId: 'castle' })
    expect(controller.teleportPlayer).toHaveBeenCalledOnce()
    wrapper.unmount()
  })
})
