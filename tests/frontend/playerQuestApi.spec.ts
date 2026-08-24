import { afterEach, describe, expect, it, vi } from 'vitest'

import { api } from '../../frontend/src/api/client'
import {
  fetchPlayerQuest,
  interactWithMissingChildQuest,
  PlayerQuestApiError,
  PlayerQuestConflictError,
  travelPlayer,
} from '../../frontend/src/api/playerQuest'
import {
  acceptedPlayerQuestFixture,
  availablePlayerQuestFixture,
} from './fixtures'


function axiosError(status: number, message: unknown) {
  return {
    name: 'AxiosError',
    message: 'unsafe transport detail',
    isAxiosError: true,
    config: { url: '/private-url' },
    response: {
      data: { success: false, data: null, message },
      status,
      statusText: 'Error',
      headers: {},
      config: {},
    },
    toJSON: () => ({}),
  }
}

describe('Player quest API adapter', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('unwraps the canonical player and quest envelope', async () => {
    const get = vi.spyOn(api, 'get').mockResolvedValue({
      data: { success: true, data: availablePlayerQuestFixture, message: 'ok' },
    } as Awaited<ReturnType<typeof api.get>>)

    await expect(fetchPlayerQuest()).resolves.toEqual(availablePlayerQuestFixture)
    expect(get).toHaveBeenCalledWith('/api/player')
  })

  it('sends only the target location when travelling', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValue({
      data: { success: true, data: acceptedPlayerQuestFixture, message: 'ok' },
    } as Awaited<ReturnType<typeof api.post>>)

    await expect(travelPlayer('castle')).resolves.toEqual(acceptedPlayerQuestFixture)
    expect(post).toHaveBeenCalledWith('/api/player/travel', {
      target_location_id: 'castle',
    })
  })

  it('sends the interaction with the caller-owned quest version', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValue({
      data: { success: true, data: acceptedPlayerQuestFixture, message: 'ok' },
    } as Awaited<ReturnType<typeof api.post>>)

    await expect(interactWithMissingChildQuest({
      interaction: 'ask_grey',
      expected_version: 1,
    })).resolves.toEqual(acceptedPlayerQuestFixture)
    expect(post).toHaveBeenCalledWith('/api/quests/missing-child/interact', {
      interaction: 'ask_grey',
      expected_version: 1,
    })
  })

  it('maps a stale quest response to a dedicated conflict error', async () => {
    vi.spyOn(api, 'post').mockRejectedValue(
      axiosError(409, 'Quest state has changed'),
    )

    await expect(interactWithMissingChildQuest({
      interaction: 'accept_quest',
      expected_version: 0,
    })).rejects.toEqual(
      new PlayerQuestConflictError('Quest state has changed'),
    )
  })

  it.each([
    [404, 'Location not found'],
    [503, 'Player quest service is unavailable'],
  ])('maps HTTP %s to a safe player quest error', async (status, message) => {
    vi.spyOn(api, 'post').mockRejectedValue(axiosError(status, message))

    await expect(travelPlayer('castle')).rejects.toEqual(
      new PlayerQuestApiError(status, message),
    )
  })

  it('normalizes unknown and malformed failures without exposing transport data', async () => {
    vi.spyOn(api, 'get').mockRejectedValue(axiosError(502, { private: true }))

    await expect(fetchPlayerQuest()).rejects.toEqual(
      new PlayerQuestApiError(502, 'Player quest request failed'),
    )
  })
})
