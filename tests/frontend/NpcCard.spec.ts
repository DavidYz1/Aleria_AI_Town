import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import NpcCard from '../../frontend/src/components/NpcCard.vue'
import { worldFixture } from './fixtures'

describe('NpcCard', () => {
  it('emits the NPC ID from an explicit detail control', async () => {
    const wrapper = mount(NpcCard, {
      props: {
        npc: worldFixture.npcs[0],
        locationName: '中央公园',
      },
    })

    expect(wrapper.get('article').text()).toContain('Ryan')
    expect(wrapper.get('article').find('dl').exists()).toBe(true)

    const detailButton = wrapper.get('button')
    expect(detailButton.text()).toBe('查看详情')

    await detailButton.trigger('click')

    expect(wrapper.emitted('select')).toEqual([['ryan']])
  })
})
