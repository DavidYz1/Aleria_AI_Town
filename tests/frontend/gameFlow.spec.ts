import { describe, expect, it } from 'vitest'

import {
  destinationAfterBoot,
  destinationAfterProfileCreated,
  destinationAfterStory,
} from '../../frontend/src/gameFlow'

const profile = {
  version: 1 as const,
  displayName: '洛恩',
  adventurerClass: 'ranger' as const,
  introCompleted: false,
}

describe('game flow destinations', () => {
  it('routes boot based on whether a profile exists and intro is complete', () => {
    expect(destinationAfterBoot(null)).toBe('create')
    expect(destinationAfterBoot({ ...profile, introCompleted: false })).toBe('story')
    expect(destinationAfterBoot({ ...profile, introCompleted: true })).toBe('town')
  })

  it('routes completed profile creation to story', () => {
    expect(destinationAfterProfileCreated()).toBe('story')
  })

  it('routes completed story to town', () => {
    expect(destinationAfterStory()).toBe('town')
  })
})
