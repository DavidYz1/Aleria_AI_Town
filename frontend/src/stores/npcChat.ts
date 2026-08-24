import { defineStore } from 'pinia'
import { reactive } from 'vue'

import { sendNpcChat } from '../api/chat'
import type { LocalPlayerProfileV1 } from '../player/playerProfile'
import type {
  ChatFetcher,
  ChatMessage,
  NpcChatData,
} from '../types/chat'


export interface NpcChatSession {
  conversationId: string | null
  messages: ChatMessage[]
  sending: boolean
  error: string | null
  pendingMessage: string
  provider: string | null
  fallbackUsed: boolean
}

export const useNpcChatStore = defineStore('npcChat', () => {
  const sessionsByNpc = reactive<Record<string, NpcChatSession>>({})
  const requestVersions = new Map<string, number>()

  function sessionFor(npcId: string): NpcChatSession {
    if (sessionsByNpc[npcId] === undefined) {
      sessionsByNpc[npcId] = {
        conversationId: null,
        messages: [],
        sending: false,
        error: null,
        pendingMessage: '',
        provider: null,
        fallbackUsed: false,
      }
    }
    return sessionsByNpc[npcId]
  }

  function setPendingMessage(npcId: string, value: string): void {
    sessionFor(npcId).pendingMessage = value
  }

  async function send(
    npcId: string,
    profile: LocalPlayerProfileV1 | null,
    fetcher: ChatFetcher = sendNpcChat,
  ): Promise<void> {
    const session = sessionFor(npcId)
    const message = session.pendingMessage.trim()
    if (message.length === 0 || session.sending) return

    const version = (requestVersions.get(npcId) ?? 0) + 1
    requestVersions.set(npcId, version)
    session.sending = true
    session.error = null

    try {
      const result = await fetcher(npcId, {
        conversation_id: session.conversationId,
        message,
        ...(profile === null
          ? {}
          : {
              player_profile: {
                display_name: profile.displayName,
                adventurer_class: profile.adventurerClass,
              },
            }),
      })
      if (requestVersions.get(npcId) !== version) return
      applyResult(session, npcId, result, message)
    } catch {
      if (requestVersions.get(npcId) !== version) return
      session.error = '消息发送失败，请稍后重试。'
    } finally {
      if (requestVersions.get(npcId) === version) {
        session.sending = false
      }
    }
  }

  async function retry(
    npcId: string,
    profile: LocalPlayerProfileV1 | null,
    fetcher: ChatFetcher = sendNpcChat,
  ): Promise<void> {
    await send(npcId, profile, fetcher)
  }

  return { sessionsByNpc, sessionFor, setPendingMessage, send, retry }
})

function applyResult(
  session: NpcChatSession,
  npcId: string,
  result: NpcChatData,
  sentMessage: string,
): void {
  if (result.npc_id !== npcId) {
    throw new Error('Chat response NPC mismatch')
  }
  session.conversationId = result.conversation_id
  session.messages.push(result.turn.user, result.turn.assistant)
  session.provider = result.provider
  session.fallbackUsed = result.fallback_used
  if (session.pendingMessage.trim() === sentMessage) {
    session.pendingMessage = ''
  }
}
