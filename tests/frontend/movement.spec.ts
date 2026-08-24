import { describe, expect, it } from 'vitest'

import { resolveVelocity } from '../../frontend/src/game/movement'


describe('resolveVelocity', () => {
  it('returns the full speed for one active direction', () => {
    expect(resolveVelocity({
      up: true,
      down: false,
      left: false,
      right: false,
    }, 160)).toEqual({ x: 0, y: -160 })
  })

  it('normalizes diagonal movement to the configured speed', () => {
    const velocity = resolveVelocity({
      up: true,
      down: false,
      left: false,
      right: true,
    }, 160)

    expect(Math.hypot(velocity.x, velocity.y)).toBeCloseTo(160)
    expect(velocity.x).toBeGreaterThan(0)
    expect(velocity.y).toBeLessThan(0)
  })

  it('cancels opposing directions without introducing drift', () => {
    expect(resolveVelocity({
      up: true,
      down: true,
      left: true,
      right: true,
    }, 160)).toEqual({ x: 0, y: 0 })
  })
})
