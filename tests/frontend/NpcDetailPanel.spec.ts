import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import NpcDetailPanel from '../../frontend/src/components/NpcDetailPanel.vue'
import type { NpcDetailData } from '../../frontend/src/types/npc'
import { npcDetailFixture } from './fixtures'


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
          tick: 1,
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
})
