import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import NpcChatPanel from '../../frontend/src/components/NpcChatPanel.vue'
import type { ChatMessage } from '../../frontend/src/types/chat'


const messages: ChatMessage[] = [
  { id: 1, role: 'user', content: '你好。' },
  {
    id: 2,
    role: 'assistant',
    content: '别担心，我会尽力帮你。',
    emotion: 'cheerful',
  },
]

function mountPanel(overrides: Record<string, unknown> = {}) {
  return mount(NpcChatPanel, {
    props: {
      selectedNpcId: 'ryan',
      npcName: 'Ryan',
      messages: [],
      sending: false,
      error: null,
      pendingMessage: '',
      provider: null,
      fallbackUsed: false,
      ...overrides,
    },
  })
}

describe('NpcChatPanel', () => {
  it('does not render when no NPC is selected', () => {
    const wrapper = mountPanel({ selectedNpcId: null })

    expect(wrapper.find('aside').exists()).toBe(false)
  })

  it('renders an accessible empty chat composer with a 500 character limit', () => {
    const wrapper = mountPanel()

    expect(wrapper.get('h2').text()).toContain('与 Ryan 对话')
    expect(wrapper.text()).toContain('还没有聊天记录。')
    const textarea = wrapper.get('textarea')
    expect(textarea.attributes('maxlength')).toBe('500')
    expect(wrapper.get('label').attributes('for')).toBe(textarea.attributes('id'))
    expect(wrapper.text()).toContain('0 / 500')
    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()
  })

  it('emits controlled draft updates and send without owning state', async () => {
    const wrapper = mountPanel({ pendingMessage: '你好' })
    const textarea = wrapper.get('textarea')

    await textarea.setValue('新的消息')
    await wrapper.get('form').trigger('submit')

    expect(wrapper.emitted('update:pendingMessage')).toEqual([['新的消息']])
    expect(wrapper.emitted('send')).toHaveLength(1)
    expect(wrapper.props('pendingMessage')).toBe('你好')
  })

  it('labels user and NPC messages with text rather than color alone', () => {
    const wrapper = mountPanel({ messages })
    const items = wrapper.findAll('.chat-message')

    expect(items).toHaveLength(2)
    expect(items[0].text()).toContain('你')
    expect(items[0].text()).toContain('你好。')
    expect(items[1].text()).toContain('Ryan')
    expect(items[1].text()).toContain('别担心，我会尽力帮你。')
  })

  it('renders message content as inert text', () => {
    const unsafe: ChatMessage[] = [
      {
        id: 3,
        role: 'assistant',
        content: '<img src=x onerror=alert(1)>',
        emotion: 'neutral',
      },
    ]
    const wrapper = mountPanel({ messages: unsafe })

    expect(wrapper.find('.chat-message img').exists()).toBe(false)
    expect(wrapper.get('.chat-message').text()).toContain(
      '<img src=x onerror=alert(1)>',
    )
  })

  it('announces sending and disables duplicate submission', () => {
    const wrapper = mountPanel({ pendingMessage: '你好', sending: true })

    expect(wrapper.get('[role="status"]').text()).toContain('正在等待回复')
    expect(wrapper.get('[role="status"]').attributes('aria-live')).toBe('polite')
    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()
  })

  it('announces an error and emits retry', async () => {
    const wrapper = mountPanel({
      pendingMessage: '你好',
      error: '消息发送失败，请稍后重试。',
    })

    const alert = wrapper.get('[role="alert"]')
    expect(alert.text()).toContain('消息发送失败，请稍后重试。')
    await alert.get('button').trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
  })

  it.each([
    [{ provider: 'mock', fallbackUsed: false }, 'Mock 模式'],
    [{ provider: 'deepseek', fallbackUsed: false }, 'AI：deepseek'],
    [{ provider: 'mock', fallbackUsed: true }, 'AI 暂不可用，已使用 Mock 回复'],
  ])('shows truthful provider status for %#', (overrides, expected) => {
    const wrapper = mountPanel(overrides)

    expect(wrapper.get('.chat-provider-status').text()).toBe(expected)
  })
})
