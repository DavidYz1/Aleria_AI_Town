import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import TickPanel from '../../frontend/src/components/TickPanel.vue'
import { tickFixture } from './fixtures'


describe('TickPanel', () => {
  it('emits one advance request from the accessible control', async () => {
    const wrapper = mount(TickPanel, {
      props: { advancing: false, error: null, tick: null },
    })

    await wrapper.get('button').trigger('click')

    expect(wrapper.get('button').text()).toBe('推进 1 小时')
    expect(wrapper.emitted('advance')).toHaveLength(1)
  })

  it('disables the control and announces request progress', () => {
    const wrapper = mount(TickPanel, {
      props: { advancing: true, error: null, tick: null },
    })

    expect(wrapper.get('button').attributes('disabled')).toBeDefined()
    expect(wrapper.get('button').text()).toBe('推进中…')
  })

  it('renders the latest action and event records', () => {
    const wrapper = mount(TickPanel, {
      props: { advancing: false, error: null, tick: tickFixture },
    })

    expect(wrapper.text()).toContain('Tick 1 · 09:00')
    for (const text of ['Ryan · 工作', 'Shir · 移动 → 中央公园', 'Grey · 工作']) {
      expect(wrapper.text()).toContain(text)
    }
    for (const event of tickFixture.events) {
      expect(wrapper.text()).toContain(event.description)
    }
  })

  it('announces a tick error without hiding the control', () => {
    const wrapper = mount(TickPanel, {
      props: { advancing: false, error: '时间推进失败，当前世界状态未改变。', tick: null },
    })

    expect(wrapper.get('[role="alert"]').text()).toContain('当前世界状态未改变')
    expect(wrapper.find('button').exists()).toBe(true)
  })
})
