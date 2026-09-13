import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { api } from '../../frontend/src/api/client'
import { useNpcMemoryStore } from '../../frontend/src/stores/npcMemory'
import { usePlayerProfileStore } from '../../frontend/src/stores/playerProfile'
import { usePlayerQuestStore } from '../../frontend/src/stores/playerQuest'
import { useWorldStore } from '../../frontend/src/stores/world'
import TownView from '../../frontend/src/views/TownView.vue'
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
    <section class="stage2-map-host" aria-label="Stage 2 测试地图">
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
    user: { ...chatResponseFixture.turn.user, content: '故障期间还能交谈吗？' },
    assistant: {
      ...chatResponseFixture.turn.assistant,
      content: '可以。记忆检索降级不会阻止我们继续交谈。',
    },
  },
}

const greyFallbackMemoryFixture = {
  ...npcMemoryExplanationsFixture,
  npc_id: 'grey',
  retrieval_mode: 'lexical_fallback' as const,
  fallback_used: true,
  memories: [
    {
      ...npcMemoryExplanationsFixture.memories[0],
      summary: 'Grey 记得自己完成了一次城堡巡查。',
      source: { kind: 'world_event' as const, label: '亲历事件' },
    },
  ],
}

function mountStage2Town(memory: () => Promise<unknown>) {
  const pinia = createPinia()
  setActivePinia(pinia)
  usePlayerProfileStore().profile = {
    version: 1,
    displayName: '洛恩',
    adventurerClass: 'ranger',
    introCompleted: true,
  }

  let currentWorld = worldFixture
  const envelope = (data: unknown) => ({
    data: { success: true, data, message: 'ok' },
  })
  const get = vi.spyOn(api, 'get').mockImplementation((url) => {
    if (url === '/api/world') {
      return Promise.resolve(envelope(currentWorld)) as ReturnType<typeof api.get>
    }
    if (url === '/api/player') {
      return Promise.resolve(envelope(availablePlayerQuestFixture)) as ReturnType<typeof api.get>
    }
    if (url === '/api/npcs/grey') {
      return Promise.resolve(envelope(greyDetailFixture)) as ReturnType<typeof api.get>
    }
    if (url === '/api/npcs/grey/memory-explanations') {
      return memory().then(envelope) as ReturnType<typeof api.get>
    }
    return Promise.reject(new Error(`Unexpected GET ${url}`)) as ReturnType<typeof api.get>
  })
  const post = vi.spyOn(api, 'post').mockImplementation((url) => {
    if (url === '/api/npcs/grey/chat') {
      return Promise.resolve(envelope(greyChatFixture)) as ReturnType<typeof api.post>
    }
    if (url === '/api/world/tick') {
      currentWorld = tickFixture.world
      return Promise.resolve(envelope(tickFixture)) as ReturnType<typeof api.post>
    }
    if (url === '/api/quests/missing-child/interact') {
      return Promise.resolve(envelope(acceptedPlayerQuestFixture)) as ReturnType<typeof api.post>
    }
    return Promise.reject(new Error(`Unexpected POST ${url}`)) as ReturnType<typeof api.post>
  })
  const wrapper = mount(TownView, {
    global: {
      plugins: [pinia],
      stubs: { TownGameHost: TownGameHostStub },
    },
  })
  return { wrapper, get, post }
}

describe('Stage 2 presentation acceptance', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('keeps map, detail, chat, tick, and quest working when memory is unavailable', async () => {
    const { wrapper, post } = mountStage2Town(
      () => Promise.reject(new Error('PRIVATE cognition DSN')),
    )
    await flushPromises()

    expect(wrapper.getComponent(TownGameHostStub).props('npcs')).toHaveLength(3)
    expect(wrapper.findAll('.location-card')).toHaveLength(4)

    await wrapper.getComponent(TownGameHostStub).get('button').trigger('click')
    await flushPromises()
    expect(wrapper.get('.npc-detail-panel').text()).toContain('Grey')
    expect(wrapper.get('.npc-detail-panel').text()).toContain('晨曦城堡')
    expect(wrapper.get('.memory-explanations').text()).toContain('暂时无法读取')
    expect(wrapper.text()).not.toContain('PRIVATE cognition DSN')

    await wrapper.get('.npc-chat-panel textarea').setValue('故障期间还能交谈吗？')
    await wrapper.get('.npc-chat-panel form').trigger('submit')
    await flushPromises()
    expect(wrapper.get('.npc-chat-panel').text()).toContain('不会阻止我们继续交谈')

    await wrapper.get('.tick-panel button').trigger('click')
    await flushPromises()
    expect(wrapper.get('.tick-result').text()).toContain('第 1 回合 · 09:00')
    expect(useWorldStore().data?.world.clock_tick).toBe(1)

    await wrapper.get('.quest-actions button').trigger('click')
    await flushPromises()
    expect(wrapper.get('.quest-panel').text()).toContain('已接受')
    expect(usePlayerQuestStore().data?.quest.status).toBe('accepted')

    expect(post.mock.calls.map(([url]) => url)).toEqual([
      '/api/npcs/grey/chat',
      '/api/world/tick',
      '/api/quests/missing-child/interact',
    ])
    expect(wrapper.find('.stage2-map-host').exists()).toBe(true)
    expect(wrapper.get('.npc-detail-panel').text()).toContain('Grey')
    expect(useNpcMemoryStore().error).toBe('相关记忆暂时无法读取，请稍后重试。')
  })

  it('shows lexical fallback safely without disabling the RPG controls', async () => {
    const { wrapper } = mountStage2Town(
      () => Promise.resolve(greyFallbackMemoryFixture),
    )
    await flushPromises()
    await wrapper.getComponent(TownGameHostStub).get('button').trigger('click')
    await flushPromises()

    const toggle = wrapper.get('.memory-explanations button[aria-controls]')
    expect(toggle.attributes('aria-expanded')).toBe('false')
    await toggle.trigger('click')

    const memory = wrapper.get('.memory-explanations')
    expect(memory.text()).toContain('关键词匹配作为降级方式检索')
    expect(memory.text()).toContain('Grey 记得自己完成了一次城堡巡查。')
    expect(memory.text()).toContain('亲历事件')
    expect(memory.text()).not.toContain('lexical_fallback')
    expect(useNpcMemoryStore().data?.retrieval_mode).toBe('lexical_fallback')
    expect(wrapper.get('.npc-chat-panel textarea').attributes('disabled')).toBeUndefined()
    expect(wrapper.get('.tick-panel button').attributes('disabled')).toBeUndefined()
    expect(wrapper.get('.quest-actions button').attributes('disabled')).toBeUndefined()
    expect(wrapper.find('.stage2-map-host').exists()).toBe(true)
  })
})
