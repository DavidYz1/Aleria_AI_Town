import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from '../../frontend/src/App.vue'
import { api } from '../../frontend/src/api/client'
import { PLAYER_PROFILE_STORAGE_KEY } from '../../frontend/src/player/playerProfile'
import { usePlayerQuestStore } from '../../frontend/src/stores/playerQuest'
import { useWorldStore } from '../../frontend/src/stores/world'
import {
  acceptedPlayerQuestFixture,
  availablePlayerQuestFixture,
  chatResponseFixture,
  npcDetailFixture,
  npcMemoryExplanationsFixture,
  tickFixture,
  worldFixture,
} from './fixtures'

const TownGameHostStub = defineComponent({
  name: 'TownGameHost',
  props: {
    profile: { type: Object, required: true },
    playerLocationId: { type: String, default: null },
    npcs: { type: Array, required: true },
  },
  emits: ['npcSelected', 'playerLocationEntered'],
  setup(_props, { expose }) {
    expose({ teleportPlayer: (_locationId: string) => undefined })
    return {}
  },
  template: `
    <section class="phase2-map-host" aria-label="曦谷测试地图">
      <button type="button" @click="$emit('npcSelected', 'grey')">选择 Grey</button>
    </section>
  `,
})

const greyDetailFixture = {
  ...npcDetailFixture,
  profile: {
    id: 'grey',
    name: 'Grey',
    role: 'Guardian',
    personality: ['reliable', 'calm', 'protective'],
  },
  state: {
    ...npcDetailFixture.state,
    location_id: 'castle',
    location_name: '晨曦城堡',
  },
}

const greyChatFixture = {
  ...chatResponseFixture,
  npc_id: 'grey',
  turn: {
    user: { ...chatResponseFixture.turn.user, content: '你认识我吗？' },
    assistant: {
      ...chatResponseFixture.turn.assistant,
      content: '洛恩，我只知道你如今选择以游侠的方式行事；你的过去仍没有可靠证据。',
    },
  },
}

const greyMemoryFixture = {
  ...npcMemoryExplanationsFixture,
  npc_id: 'grey',
  memories: [
    {
      ...npcMemoryExplanationsFixture.memories[0],
      summary: '在晨曦城堡完成了一次日常巡查。',
    },
    {
      ...npcMemoryExplanationsFixture.memories[1],
      summary: 'Grey 对自己的守护职责有稳定认识。',
    },
  ],
}

function mountPhase2App() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return mount(App, {
    global: {
      plugins: [pinia],
      stubs: { TownGameHost: TownGameHostStub },
    },
  })
}

function mockInitialLoads() {
  return vi.spyOn(api, 'get').mockImplementation((url) => {
    const data = url === '/api/world'
      ? worldFixture
      : url === '/api/player'
        ? availablePlayerQuestFixture
        : url === '/api/npcs/grey'
          ? greyDetailFixture
          : url === '/api/npcs/grey/memory-explanations'
            ? greyMemoryFixture
            : null
    if (data === null) {
      return Promise.reject(new Error(`Unexpected GET ${url}`)) as ReturnType<typeof api.get>
    }
    return Promise.resolve({
      data: { success: true, data, message: 'ok' },
    }) as ReturnType<typeof api.get>
  })
}

const forbiddenCoordinateKeys = new Set([
  'x',
  'y',
  'player_x',
  'player_y',
  'playerX',
  'playerY',
  'position_x',
  'position_y',
  'positionX',
  'positionY',
])

function expectNoCoordinateKeys(value: unknown): void {
  if (Array.isArray(value)) {
    value.forEach(expectNoCoordinateKeys)
    return
  }
  if (value === null || typeof value !== 'object') return

  Object.entries(value).forEach(([key, nestedValue]) => {
    expect(forbiddenCoordinateKeys.has(key)).toBe(false)
    expectNoCoordinateKeys(nestedValue)
  })
}

describe('Phase 2 presentation acceptance', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('completes first-time onboarding and chats from the Backend NPC map projection', async () => {
    mockInitialLoads()
    const post = vi.spyOn(api, 'post').mockResolvedValue({
      data: { success: true, data: greyChatFixture, message: 'ok' },
    } as Awaited<ReturnType<typeof api.post>>)
    const wrapper = mountPhase2App()

    expect(wrapper.find('[data-scene="boot"]').exists()).toBe(true)
    await wrapper.get('[data-action="continue"]').trigger('click')
    await wrapper.get('input[name="displayName"]').setValue('洛恩')
    await wrapper.get('[data-class="ranger"]').trigger('click')
    await wrapper.get('form').trigger('submit')
    expect(wrapper.get('[data-scene="story"]').text()).toContain('洛恩')
    await wrapper.get('[data-action="skip-story"]').trigger('click')
    await flushPromises()

    const host = wrapper.getComponent(TownGameHostStub)
    expect(host.props('npcs')).toEqual([
      expect.objectContaining({ id: 'ryan', anchorName: 'location:park' }),
      expect.objectContaining({ id: 'shir', anchorName: 'location:tavern' }),
      expect.objectContaining({ id: 'grey', anchorName: 'location:castle' }),
    ])
    expect(useWorldStore().data?.world.clock_tick).toBe(0)
    expect(usePlayerQuestStore().data?.quest.version).toBe(0)

    await host.get('button').trigger('click')
    await flushPromises()
    expect(wrapper.get('.npc-detail-panel').text()).toContain('Grey')
    expect(wrapper.get('.memory-explanations').text()).toContain('共 2 条')
    expect(wrapper.get('.npc-chat-panel').text()).toContain('与 Grey 对话')
    await wrapper.get('.npc-chat-panel textarea').setValue('你认识我吗？')
    await wrapper.get('.npc-chat-panel form').trigger('submit')
    await flushPromises()

    expect(post).toHaveBeenCalledWith('/api/npcs/grey/chat', {
      conversation_id: null,
      message: '你认识我吗？',
      player_profile: {
        display_name: '洛恩',
        adventurer_class: 'ranger',
      },
    })
    expect(wrapper.get('.npc-chat-panel').text()).toContain('你的过去仍没有可靠证据')
    expect(useWorldStore().data?.world.clock_tick).toBe(0)
    expect(usePlayerQuestStore().data?.quest.version).toBe(0)
  })

  it('loads a completed profile directly and keeps Phaser movement separate from Backend mutations', async () => {
    localStorage.setItem(PLAYER_PROFILE_STORAGE_KEY, JSON.stringify({
      version: 1,
      displayName: '弥娅',
      adventurerClass: 'cleric',
      introCompleted: true,
    }))
    const get = mockInitialLoads()
    const post = vi.spyOn(api, 'post').mockImplementation((url) => {
      const data = url === '/api/world/tick'
        ? tickFixture
        : acceptedPlayerQuestFixture
      return Promise.resolve({
        data: { success: true, data, message: 'ok' },
      }) as ReturnType<typeof api.post>
    })
    const wrapper = mountPhase2App()

    await wrapper.get('[data-action="continue"]').trigger('click')
    await flushPromises()

    const host = wrapper.getComponent(TownGameHostStub)
    expect(host.props('profile')).toMatchObject({
      displayName: '弥娅',
      adventurerClass: 'cleric',
    })
    expect(get).toHaveBeenCalledTimes(2)
    expect(get).toHaveBeenCalledWith('/api/world')
    expect(get).toHaveBeenCalledWith('/api/player')
    expect(post).not.toHaveBeenCalled()

    await wrapper.get('.tick-panel button').trigger('click')
    await flushPromises()
    // Live planning makes a tick a 30-50s call. The third argument is what keeps
    // the 5s client default from aborting a request the server still completes,
    // so assert the ceiling is really raised rather than just tolerating the arg.
    const tickCall = post.mock.calls.find(([url]) => url === '/api/world/tick')
    expect(tickCall, 'tick 请求必须真的发出过，否则下面的断言无从谈起').toBeDefined()
    expect(tickCall![1]).toEqual({ expected_world_version: 0 })
    expect((tickCall![2] as { timeout: number }).timeout).toBeGreaterThan(30_000)
    expect(host.props('npcs')).toEqual([
      expect.objectContaining({ id: 'ryan', anchorName: 'location:park' }),
      expect.objectContaining({ id: 'shir', anchorName: 'location:park' }),
      expect.objectContaining({ id: 'grey', anchorName: 'location:castle' }),
    ])

    const castle = wrapper.findAll('.location-card').find(
      (card) => card.get('h3').text() === '晨曦城堡',
    )
    await castle!.get('button').trigger('click')
    await flushPromises()
    // 本断言的目的是「Phaser 移动不打后端」：调用序列与载荷必须逐项精确。
    // 只把每次调用的 axios config 摘掉 —— tick 的超时覆盖在上面单独断言过了。
    expect(post.mock.calls.map(([url, payload]) => [url, payload])).toEqual([
      ['/api/world/tick', { expected_world_version: 0 }],
      ['/api/player/travel', { target_location_id: 'castle', expected_world_version: 1 }],
    ])
    post.mock.calls.forEach(([, payload]) => expectNoCoordinateKeys(payload))
  })
})
