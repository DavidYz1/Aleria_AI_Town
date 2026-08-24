import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import QuestPanel from '../../frontend/src/components/QuestPanel.vue'
import type { QuestData } from '../../frontend/src/types/playerQuest'
import {
  acceptedPlayerQuestFixture,
  availablePlayerQuestFixture,
} from './fixtures'


describe('QuestPanel', () => {
  it('renders Backend-derived status, objective, and available action', () => {
    const wrapper = mount(QuestPanel, {
      props: {
        quest: acceptedPlayerQuestFixture.quest,
        mutating: false,
        mutationError: null,
      },
    })

    expect(wrapper.get('h3').text()).toBe('失踪的孩子')
    expect(wrapper.text()).toContain('已接受')
    expect(wrapper.text()).toContain('前往晨曦城堡询问 Grey。')
    expect(wrapper.findAll('.quest-actions button')).toHaveLength(1)
    expect(wrapper.get('.quest-actions button').text()).toBe('询问 Grey')
  })

  it('emits the selected interaction ID', async () => {
    const wrapper = mount(QuestPanel, {
      props: {
        quest: availablePlayerQuestFixture.quest,
        mutating: false,
        mutationError: null,
      },
    })

    await wrapper.get('.quest-actions button').trigger('click')
    expect(wrapper.emitted('interact')).toEqual([['accept_quest']])
  })

  it('keeps the quest visible while disabling duplicate interaction', () => {
    const wrapper = mount(QuestPanel, {
      props: {
        quest: acceptedPlayerQuestFixture.quest,
        mutating: true,
        mutationError: null,
      },
    })

    expect(wrapper.text()).toContain(acceptedPlayerQuestFixture.quest.objective)
    expect(wrapper.get('.quest-actions button').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[role="status"]').text()).toContain('正在更新任务')
  })

  it('announces mutation errors without hiding the last good quest state', () => {
    const wrapper = mount(QuestPanel, {
      props: {
        quest: acceptedPlayerQuestFixture.quest,
        mutating: false,
        mutationError: '操作失败，当前玩家与任务状态未改变。',
      },
    })

    expect(wrapper.get('[role="alert"]').text()).toContain('状态未改变')
    expect(wrapper.text()).toContain(acceptedPlayerQuestFixture.quest.objective)
  })

  it('renders a completed state without another action', () => {
    const completed: QuestData = {
      ...acceptedPlayerQuestFixture.quest,
      status: 'completed',
      version: 5,
      objective: '任务已完成。',
      available_interactions: [],
    }
    const wrapper = mount(QuestPanel, {
      props: { quest: completed, mutating: false, mutationError: null },
    })

    expect(wrapper.text()).toContain('已完成')
    expect(wrapper.text()).toContain('任务已经完成')
    expect(wrapper.find('.quest-actions button').exists()).toBe(false)
  })

  it('renders recent event descriptions as text rather than HTML', () => {
    const wrapper = mount(QuestPanel, {
      props: {
        quest: {
          ...acceptedPlayerQuestFixture.quest,
          recent_events: [{
            ...acceptedPlayerQuestFixture.quest.recent_events[0],
            description: '<strong>接受委托</strong>',
          }],
        },
        mutating: false,
        mutationError: null,
      },
    })

    expect(wrapper.text()).toContain('<strong>接受委托</strong>')
    expect(wrapper.find('.quest-history strong').exists()).toBe(false)
  })
})
