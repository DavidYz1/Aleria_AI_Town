import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import NpcDetailPanel from '../../frontend/src/components/NpcDetailPanel.vue'
import type {
  NpcDetailData,
  NpcMemoryExplanationsData,
} from '../../frontend/src/types/npc'
import { npcDetailFixture, npcMemoryExplanationsFixture } from './fixtures'


function mountPanel(props: Record<string, unknown> = {}) {
  return mount(NpcDetailPanel, {
    props: {
      selectedNpcId: 'ryan',
      detail: npcDetailFixture,
      loading: false,
      error: null,
      memory: null,
      memoryLoading: false,
      memoryError: null,
      ...props,
    },
  })
}

function memoryToggle(wrapper: ReturnType<typeof mountPanel>) {
  return wrapper.get('.memory-explanations button[aria-controls]')
}


describe('NpcDetailPanel', () => {
  it('does not render an aside when no NPC is selected', () => {
    const wrapper = mount(NpcDetailPanel, {
      props: {
        selectedNpcId: null,
        detail: null,
        loading: false,
        error: null,
      },
    })

    expect(wrapper.find('aside').exists()).toBe(false)
  })

  it('announces the initial loading state', () => {
    const wrapper = mount(NpcDetailPanel, {
      props: {
        selectedNpcId: 'ryan',
        detail: null,
        loading: true,
        error: null,
      },
    })

    expect(wrapper.get('[role="status"]').text()).toContain(
      '正在读取居民档案…',
    )
  })

  it('announces an error and emits retry from its action', async () => {
    const wrapper = mount(NpcDetailPanel, {
      props: {
        selectedNpcId: 'ryan',
        detail: null,
        loading: false,
        error: '居民详情加载失败，请稍后重试。',
      },
    })

    const alert = wrapper.get('[role="alert"]')
    expect(alert.text()).toContain('居民详情加载失败，请稍后重试。')
    await alert.get('button').trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
  })

  it('provides an accessible close control and emits close', async () => {
    const wrapper = mount(NpcDetailPanel, {
      props: {
        selectedNpcId: 'ryan',
        detail: npcDetailFixture,
        loading: false,
        error: null,
      },
    })

    const close = wrapper.get('button[aria-label="关闭居民详情"]')
    await close.trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('renders the legitimate empty-history state', () => {
    const detailWithoutHistory: NpcDetailData = {
      ...npcDetailFixture,
      recent_actions: [],
    }
    const wrapper = mount(NpcDetailPanel, {
      props: {
        selectedNpcId: 'ryan',
        detail: detailWithoutHistory,
        loading: false,
        error: null,
      },
    })

    expect(wrapper.text()).toContain('还没有已记录的行动。')
  })

  it('renders the complete NPC detail and readable target action', () => {
    const detailWithTarget: NpcDetailData = {
      ...npcDetailFixture,
      recent_actions: [
        {
          id: 2,
          clock_tick: 1,
          world_time: '09:00',
          action_type: 'move',
          target_kind: 'location',
          target_id: 'tavern',
          target_name: '星辰酒馆',
          reason_code: 'low_mood_find_food',
          reason_text: '心情较低，因此前往星辰酒馆用餐。',
        },
      ],
    }
    const wrapper = mount(NpcDetailPanel, {
      props: {
        selectedNpcId: 'ryan',
        detail: detailWithTarget,
        loading: false,
        error: null,
      },
    })

    const aside = wrapper.get('aside')
    expect(aside.attributes('aria-labelledby')).toBe('npc-detail-heading')
    expect(wrapper.get('#npc-detail-heading').text()).toBe('Ryan')
    for (const text of [
      'Knight',
      'optimistic',
      'brave',
      'kind',
      '中央公园',
      'Energy',
      '70',
      'Mood',
      '75',
      'Social',
      '67',
      'Day 1 · 09:00 · morning',
    ]) {
      expect(wrapper.text()).toContain(text)
    }

    const history = wrapper.get('[aria-label="最近行动"]')
    expect(history.text()).toContain('移动 → 星辰酒馆')
    expect(history.text()).toContain('心情较低，因此前往星辰酒馆用餐。')
  })

  it('keeps the related memory section collapsed by default', () => {
    const wrapper = mountPanel({ memory: npcMemoryExplanationsFixture })

    const toggle = wrapper.get('button[aria-expanded="false"]')
    expect(toggle.text()).toContain('相关记忆')
    expect(wrapper.find('.memory-list').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('在中央公园完成了一次骑士日常训练。')
    expect(wrapper.text()).toContain('共 2 条')
  })

  it('resolves aria-controls to a region that stays mounted while collapsed', async () => {
    const wrapper = mountPanel({ memory: npcMemoryExplanationsFixture })
    const controls = memoryToggle(wrapper).attributes('aria-controls')

    const collapsed = wrapper.get(`#${controls}`)
    expect(collapsed.find('.memory-list').exists()).toBe(false)
    expect(collapsed.text()).toBe('')

    await memoryToggle(wrapper).trigger('click')

    expect(wrapper.get(`#${controls}`).find('.memory-list').exists()).toBe(true)
  })

  it('treats a shape-invalid memory payload as unavailable rather than empty', async () => {
    const malformed = {
      npc_id: 'ryan',
      retrieval_mode: 'hybrid',
      fallback_used: false,
    } as unknown as NpcMemoryExplanationsData
    const wrapper = mountPanel({ memory: malformed })

    expect(wrapper.get('.memory-explanations').text()).toContain('暂时无法读取')
    expect(wrapper.text()).not.toContain('暂无可公开的记忆')

    await memoryToggle(wrapper).trigger('click')

    expect(wrapper.text()).not.toContain('这位居民暂时没有可以公开说明的记忆。')
    expect(wrapper.get('.memory-explanations [role="alert"]').text()).toContain(
      '无法读取',
    )
  })

  it('expands into the public memory list with source labels and ticks', async () => {
    const wrapper = mountPanel({ memory: npcMemoryExplanationsFixture })

    await memoryToggle(wrapper).trigger('click')

    const toggle = memoryToggle(wrapper)
    expect(toggle.attributes('aria-expanded')).toBe('true')
    const list = wrapper.get(`#${toggle.attributes('aria-controls')}`)
    for (const text of [
      '亲历事件',
      '在中央公园完成了一次骑士日常训练。',
      '这件事刚刚发生不久，这位居民印象还很清晰。',
      '第 1 回合',
      '稳定知识',
      'Ryan 对自己的骑士职责有稳定认识。',
      '第 0 回合',
    ]) {
      expect(list.text()).toContain(text)
    }
    expect(wrapper.text()).not.toContain('hybrid')
    expect(wrapper.text()).not.toContain('lexical_fallback')
    expect(wrapper.text()).not.toContain('episodic')
  })

  it('explains the degraded retrieval without naming an internal mode', async () => {
    const degraded: NpcMemoryExplanationsData = {
      ...npcMemoryExplanationsFixture,
      retrieval_mode: 'lexical_fallback',
      fallback_used: true,
    }
    const wrapper = mountPanel({ memory: degraded })

    await memoryToggle(wrapper).trigger('click')

    expect(wrapper.text()).toContain('关键词匹配')
    expect(wrapper.text()).not.toContain('lexical_fallback')
  })

  it('renders the legitimate empty memory state only once expanded', async () => {
    const empty: NpcMemoryExplanationsData = {
      ...npcMemoryExplanationsFixture,
      memories: [],
    }
    const wrapper = mountPanel({ memory: empty })

    expect(wrapper.text()).toContain('暂无可公开的记忆')
    expect(wrapper.text()).not.toContain('这位居民暂时没有可以公开说明的记忆。')

    await memoryToggle(wrapper).trigger('click')

    expect(wrapper.text()).toContain('这位居民暂时没有可以公开说明的记忆。')
  })

  it('announces the memory loading state while the detail stays readable', () => {
    const wrapper = mountPanel({ memoryLoading: true })

    expect(wrapper.get('.memory-explanations').text()).toContain('正在读取')
    expect(wrapper.get('[aria-label="最近行动"]').text()).toContain('骑士训练')
  })

  it('keeps the detail readable when only the memory read fails and emits retry-memory', async () => {
    const wrapper = mountPanel({ memoryError: '相关记忆暂时无法读取，请稍后重试。' })

    expect(wrapper.get('.detail-content').text()).toContain('中央公园')
    expect(wrapper.get('.memory-explanations').text()).toContain('暂时无法读取')

    await memoryToggle(wrapper).trigger('click')
    const alert = wrapper.get('.memory-explanations [role="alert"]')
    expect(alert.text()).toContain('相关记忆暂时无法读取，请稍后重试。')
    await alert.get('button').trigger('click')

    expect(wrapper.emitted('retry-memory')).toHaveLength(1)
    expect(wrapper.emitted('retry')).toBeUndefined()
  })

  it('does not render the memory section without a loaded detail', () => {
    const wrapper = mountPanel({
      detail: null,
      memory: npcMemoryExplanationsFixture,
    })

    expect(wrapper.find('.memory-explanations').exists()).toBe(false)
  })
})
