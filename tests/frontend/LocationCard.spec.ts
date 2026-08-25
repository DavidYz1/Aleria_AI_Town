import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import LocationCard from '../../frontend/src/components/LocationCard.vue'
import { worldFixture } from './fixtures'


describe('LocationCard', () => {
  const tavern = worldFixture.locations[0]

  it('marks the current location and disables redundant travel', () => {
    const wrapper = mount(LocationCard, {
      props: {
        location: tavern,
        isCurrent: true,
        travelling: false,
      },
    })

    expect(wrapper.classes()).toContain('is-current')
    expect(wrapper.get('button').text()).toBe('当前位置')
    expect(wrapper.get('button').attributes('disabled')).toBeDefined()
  })

  it('emits only the selected location ID', async () => {
    const wrapper = mount(LocationCard, {
      props: {
        location: tavern,
        isCurrent: false,
        travelling: false,
      },
    })

    await wrapper.get('button').trigger('click')
    expect(wrapper.get('button').text()).toBe('快速前往')
    expect(wrapper.emitted('travel')).toEqual([['tavern']])
    expect(wrapper.text()).toContain(tavern.name)
    expect(wrapper.text()).toContain(tavern.description)
  })

  it('disables travel while any location mutation is pending', () => {
    const wrapper = mount(LocationCard, {
      props: {
        location: tavern,
        isCurrent: false,
        travelling: true,
      },
    })

    expect(wrapper.get('button').attributes('disabled')).toBeDefined()
    expect(wrapper.get('button').text()).toBe('旅行中…')
  })
})
