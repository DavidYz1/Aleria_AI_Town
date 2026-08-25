import { afterEach, describe, expect, it, vi } from 'vitest'

import { api } from '../../frontend/src/api/client'
import {
  DemoResetApiError,
  resetDemo,
} from '../../frontend/src/api/demo'


describe('Demo reset API adapter', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('posts the reset command and unwraps the canonical reset summary', async () => {
    const data = {
      world_id: 'aleria-town',
      world_tick: 0,
      player_location_id: 'tavern',
      quest_status: 'available',
    }
    const post = vi.spyOn(api, 'post').mockResolvedValue({
      data: { success: true, data, message: 'Demo world reset' },
    } as Awaited<ReturnType<typeof api.post>>)

    await expect(resetDemo()).resolves.toEqual(data)
    expect(post).toHaveBeenCalledWith('/api/demo/reset')
  })

  it('normalizes reset failures without exposing transport details', async () => {
    vi.spyOn(api, 'post').mockRejectedValue(new Error('private transport detail'))

    await expect(resetDemo()).rejects.toEqual(
      new DemoResetApiError('Demo reset failed'),
    )
  })
})
