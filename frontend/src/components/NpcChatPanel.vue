<script setup lang="ts">
import { computed } from 'vue'

import type { ChatMessage } from '../types/chat'

const props = defineProps<{
  selectedNpcId: string | null
  npcName: string
  messages: ChatMessage[]
  sending: boolean
  error: string | null
  pendingMessage: string
  provider: string | null
  fallbackUsed: boolean
}>()

const emit = defineEmits<{
  'update:pendingMessage': [value: string]
  send: []
  retry: []
}>()

const canSend = computed(
  () => props.pendingMessage.trim().length > 0 && !props.sending,
)
const providerStatus = computed(() => {
  if (props.fallbackUsed) return 'AI 暂不可用，已使用 Mock 回复'
  if (props.provider === 'mock') return 'Mock 模式'
  if (props.provider !== null) return `AI：${props.provider}`
  return '尚未开始对话'
})

function updatePendingMessage(event: Event): void {
  emit('update:pendingMessage', (event.target as HTMLTextAreaElement).value)
}
</script>

<template>
  <aside
    v-if="selectedNpcId"
    class="npc-chat-panel"
    aria-labelledby="npc-chat-heading"
  >
    <header class="chat-header">
      <div>
        <p class="chat-label">Resident chat</p>
        <h2 id="npc-chat-heading">与 {{ npcName }} 对话</h2>
      </div>
      <p class="chat-provider-status">{{ providerStatus }}</p>
    </header>

    <section class="chat-history" aria-label="聊天记录">
      <p v-if="messages.length === 0" class="chat-empty">
        还没有聊天记录。向 {{ npcName }} 打个招呼吧。
      </p>
      <ol v-else>
        <li
          v-for="message in messages"
          :key="message.id"
          class="chat-message"
          :class="`is-${message.role}`"
        >
          <p class="message-speaker">
            {{ message.role === 'user' ? '你' : npcName }}
          </p>
          <p class="message-content">{{ message.content }}</p>
        </li>
      </ol>
    </section>

    <p
      v-if="sending"
      class="chat-sending"
      role="status"
      aria-live="polite"
    >
      正在等待回复…
    </p>

    <div v-if="error" class="chat-error" role="alert">
      <p>{{ error }}</p>
      <button type="button" :disabled="sending" @click="$emit('retry')">
        重试发送
      </button>
    </div>

    <form class="chat-composer" @submit.prevent="$emit('send')">
      <label for="npc-chat-message">给 {{ npcName }} 留言</label>
      <textarea
        id="npc-chat-message"
        :value="pendingMessage"
        maxlength="500"
        rows="4"
        aria-describedby="npc-chat-length"
        placeholder="输入你想说的话…"
        @input="updatePendingMessage"
      />
      <div class="composer-footer">
        <span id="npc-chat-length">{{ pendingMessage.length }} / 500</span>
        <button type="submit" :disabled="!canSend">发送消息</button>
      </div>
    </form>
  </aside>
</template>

<style scoped>
.npc-chat-panel {
  padding: 1.35rem;
  border: 1px solid #aebbac;
  border-left: 0.35rem solid #b36a32;
  border-radius: 0.9rem;
  background: rgb(252 252 247 / 94%);
  box-shadow: 0 1rem 2.5rem rgb(50 66 53 / 10%);
}

.chat-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid #c4cbc0;
}

.chat-label {
  margin: 0;
  color: #586b5d;
  font-size: 0.72rem;
  font-weight: 750;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.chat-header h2 {
  margin: 0.3rem 0 0;
  color: #1f3d2a;
  font-family: Georgia, "Times New Roman", serif;
  font-size: 1.55rem;
  font-weight: 500;
}

.chat-provider-status {
  margin: 0;
  padding: 0.35rem 0.55rem;
  border-radius: 999px;
  color: #68451f;
  background: #f2e4d2;
  font-size: 0.72rem;
  text-align: right;
}

.chat-history {
  max-height: 24rem;
  overflow-y: auto;
  padding: 1rem 0;
}

.chat-empty {
  margin: 0;
  padding: 1rem;
  border-radius: 0.65rem;
  color: #59645c;
  background: #edf0e8;
  line-height: 1.55;
}

.chat-history ol {
  display: grid;
  gap: 0.75rem;
  margin: 0;
  padding: 0;
  list-style: none;
}

.chat-message {
  max-width: 88%;
  padding: 0.75rem 0.85rem;
  border-radius: 0.7rem;
  background: #edf0e8;
}

.chat-message.is-user {
  justify-self: end;
  background: #f2e4d2;
}

.message-speaker {
  margin: 0 0 0.25rem;
  color: #586b5d;
  font-size: 0.72rem;
  font-weight: 750;
}

.message-content {
  margin: 0;
  color: #253027;
  line-height: 1.55;
  white-space: pre-wrap;
}

.chat-sending,
.chat-error {
  margin: 0 0 0.75rem;
  padding: 0.75rem 0.85rem;
  border-radius: 0.65rem;
}

.chat-sending {
  color: #536057;
  background: #edf0e8;
}

.chat-error {
  border: 1px solid #b36f61;
  color: #7d392f;
  background: #f7ece8;
}

.chat-error p {
  margin: 0 0 0.65rem;
}

.chat-error button {
  padding: 0.5rem 0.7rem;
}

.chat-composer {
  display: grid;
  gap: 0.55rem;
  padding-top: 1rem;
  border-top: 1px solid #c4cbc0;
}

.chat-composer label {
  color: #315b45;
  font-size: 0.82rem;
  font-weight: 700;
}

.chat-composer textarea {
  width: 100%;
  resize: vertical;
  padding: 0.75rem;
  border: 1px solid #aebbac;
  border-radius: 0.6rem;
  color: #253027;
  background: #fff;
  font: inherit;
  line-height: 1.5;
}

.chat-composer textarea:focus-visible {
  outline: 3px solid #d18a32;
  outline-offset: 2px;
}

.composer-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.composer-footer span {
  color: #68746b;
  font-size: 0.75rem;
  font-variant-numeric: tabular-nums;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

@media (max-width: 520px) {
  .chat-header {
    display: grid;
  }

  .chat-provider-status {
    justify-self: start;
    text-align: left;
  }
}
</style>
