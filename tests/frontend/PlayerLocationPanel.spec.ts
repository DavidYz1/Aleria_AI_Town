import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import PlayerLocationPanel from '../../frontend/src/components/PlayerLocationPanel.vue'
import { availablePlayerQuestFixture } from './fixtures'


describe('PlayerLocationPanel', () => {
  it('announces initial loading without inventing a location', () => {
    const wrapper = mount(PlayerLocationPanel, {
      props: { player: null, loading: true, error: null },
    })

    expect(wrapper.get('[role="status"]').text()).toContain('正在读取玩家位置')
    expect(wrapper.text()).not.toContain('星辉酒馆')
  })

  it('renders a safe load error and emits retry', async () => {
    const wrapper = mount(PlayerLocationPanel, {
      props: {
        player: null,
        loading: false,
        error: '玩家任务加载失败，请稍后重试。',
      },
    })

    expect(wrapper.get('[role="alert"]').text()).toContain('玩家任务加载失败')
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
  })

  it('shows the authoritative player location while preserving refresh state', () => {
    const wrapper = mount(PlayerLocationPanel, {
      props: {
        player: availablePlayerQuestFixture.player,
        loading: true,
        error: null,
      },
    })

    expect(wrapper.text()).toContain('当前位置')
    expect(wrapper.get('h3').text()).toBe('星辉酒馆')
    expect(wrapper.text()).toContain('失去记忆')
    expect(wrapper.text()).toContain('无法解释的印记')
    expect(wrapper.get('[role="status"]').text()).toContain('正在刷新')
  })
})
