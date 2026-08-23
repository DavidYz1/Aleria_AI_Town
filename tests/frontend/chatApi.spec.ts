import { afterEach, describe, expect, it, vi } from 'vitest'

import { api } from '../../frontend/src/api/client'
import {
  ChatApiError,
  sendNpcChat,
} from '../../frontend/src/api/chat'
import { chatResponseFixture } from './fixtures'


function axiosError(status: number, message: string) {
  return {
    name: 'AxiosError',
    message: 'unsafe transport detail',
    isAxiosError: true,
    config: {},
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

describe('Chat API adapter', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('encodes the NPC ID, sends a first-turn body, and unwraps the envelope', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValue({
      data: { success: true, data: chatResponseFixture, message: 'ok' },
    } as Awaited<ReturnType<typeof api.post>>)

    await expect(sendNpcChat('ryan/name', {
      conversation_id: null,
      message: '你害怕史莱姆吗？',
    })).resolves.toEqual(chatResponseFixture)
    expect(post).toHaveBeenCalledWith(
      '/api/npcs/ryan%2Fname/chat',
      { conversation_id: null, message: '你害怕史莱姆吗？' },
    )
  })

  it('sends the existing conversation ID on subsequent turns', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValue({
      data: { success: true, data: chatResponseFixture, message: 'ok' },
    } as Awaited<ReturnType<typeof api.post>>)

    await sendNpcChat('ryan', {
      conversation_id: '5e547c21-a228-4e86-940d-a1bf5d65702f',
      message: '继续聊聊吧。',
    })

    expect(post).toHaveBeenCalledWith('/api/npcs/ryan/chat', {
      conversation_id: '5e547c21-a228-4e86-940d-a1bf5d65702f',
      message: '继续聊聊吧。',
    })
  })

  it.each([
    [404, 'Conversation not found'],
    [503, 'Chat service is unavailable'],
  ])('converts HTTP %s into a safe ChatApiError', async (status, message) => {
    vi.spyOn(api, 'post').mockRejectedValue(axiosError(status, message))

    const request = sendNpcChat('ryan', {
      conversation_id: null,
      message: '你好',
    })

    await expect(request).rejects.toEqual(
      new ChatApiError(status, message),
    )
  })

  it('normalizes transport failures without exposing their message', async () => {
    vi.spyOn(api, 'post').mockRejectedValue(axiosError(502, 'private detail'))

    const request = sendNpcChat('ryan', {
      conversation_id: null,
      message: '你好',
    })

    await expect(request).rejects.toEqual(
      new ChatApiError(502, 'Chat request failed'),
    )
  })
})
