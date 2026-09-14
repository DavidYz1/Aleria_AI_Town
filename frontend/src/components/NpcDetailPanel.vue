<script setup lang="ts">
import { computed, ref } from 'vue'

import NpcThoughtTab from './NpcThoughtTab.vue'
import type { NpcDetailData, NpcMemoryExplanationsData } from '../types/npc'

const props = withDefaults(defineProps<{
  selectedNpcId: string | null
  detail: NpcDetailData | null
  loading: boolean
  error: string | null
  memory?: NpcMemoryExplanationsData | null
  memoryLoading?: boolean
  memoryError?: string | null
}>(), {
  memory: null,
  memoryLoading: false,
  memoryError: null,
})

defineEmits<{
  close: []
  retry: []
  'retry-memory': []
}>()

type MemoryState = 'loading' | 'failed' | 'unread' | 'empty' | 'ready'
type DetailTab = 'profile' | 'thought'

const TABS = [
  { id: 'profile', label: '档案' },
  { id: 'thought', label: '思考' },
] as const satisfies readonly { id: DetailTab; label: string }[]

// The selection survives switching residents on purpose: during a demo you keep
// clicking through NPCs while staying on the same view.
const activeTab = ref<DetailTab>('profile')

function focusTab(offset: number, event: KeyboardEvent): void {
  const index = TABS.findIndex((tab) => tab.id === activeTab.value)
  const next = TABS[(index + offset + TABS.length) % TABS.length]
  activeTab.value = next.id
  const list = (event.currentTarget as HTMLElement).parentElement
  list?.querySelector<HTMLElement>(`#npc-tab-${next.id}`)?.focus()
}

const MALFORMED_MEMORY_MESSAGE = '相关记忆暂时无法读取，请稍后重试。'

const memoryExpanded = ref(false)
// A response body is external data, not a compiler guarantee. A shape the API
// contract forbids has to read as unavailable; rendering it as an empty list
// would state "this resident recalls nothing" without knowing that.
const memoryItems = computed(() => {
  const memories = props.memory?.memories
  return Array.isArray(memories) ? memories : []
})
const memoryFailure = computed(() => {
  if (props.memoryError !== null) return props.memoryError
  return props.memory !== null && !Array.isArray(props.memory.memories)
    ? MALFORMED_MEMORY_MESSAGE
    : null
})
const memoryState = computed<MemoryState>(() => {
  if (props.memoryLoading) return 'loading'
  if (memoryFailure.value !== null) return 'failed'
  if (props.memory === null) return 'unread'
  return memoryItems.value.length === 0 ? 'empty' : 'ready'
})
const memoryStatus = computed(() => {
  if (memoryState.value === 'loading') return '正在读取…'
  if (memoryState.value === 'failed') return '暂时无法读取'
  if (memoryState.value === 'unread') return '尚未读取'
  return memoryState.value === 'empty'
    ? '暂无可公开的记忆'
    : `共 ${memoryItems.value.length} 条`
})

const actionLabels = {
  move: '移动',
  rest: '休息',
  work: '工作',
  eat: '用餐',
  talk: '交谈',
  wait: '等待',
} as const

const needLabels = {
  energy: 'Energy',
  mood: 'Mood',
  social: 'Social',
} as const
</script>

<template>
  <aside
    v-if="selectedNpcId"
    class="npc-detail-panel"
    aria-labelledby="npc-detail-heading"
  >
    <header class="detail-header">
      <div>
        <p class="detail-label">居民档案</p>
        <h2 id="npc-detail-heading">
          {{ detail?.profile.name ?? selectedNpcId }}
        </h2>
      </div>
      <button
        type="button"
        class="detail-close"
        aria-label="关闭居民详情"
        @click="$emit('close')"
      >
        关闭
      </button>
    </header>

    <p v-if="loading" class="detail-status" role="status" aria-live="polite">
      正在读取居民档案…
    </p>

    <div v-if="error" class="detail-error" role="alert">
      <p>{{ error }}</p>
      <button type="button" @click="$emit('retry')">重新读取</button>
    </div>

    <template v-if="detail">
      <div class="detail-tabs" role="tablist" aria-label="居民详情视图">
        <button
          v-for="tab in TABS"
          :id="`npc-tab-${tab.id}`"
          :key="tab.id"
          type="button"
          role="tab"
          :aria-selected="activeTab === tab.id"
          :aria-controls="`npc-panel-${tab.id}`"
          :tabindex="activeTab === tab.id ? 0 : -1"
          @click="activeTab = tab.id"
          @keydown.left.prevent="focusTab(-1, $event)"
          @keydown.right.prevent="focusTab(1, $event)"
        >
          {{ tab.label }}
        </button>
      </div>

      <!-- Profile keeps its DOM while hidden so switching back is free; the
           thought panel is mounted on demand so opening the resident does not
           fetch a plan nobody asked to see. -->
      <div
        v-show="activeTab === 'profile'"
        id="npc-panel-profile"
        class="detail-content"
        role="tabpanel"
        aria-labelledby="npc-tab-profile"
      >
        <section class="profile-summary" aria-labelledby="profile-heading">
          <p class="detail-label">Profile</p>
          <h3 id="profile-heading">{{ detail.profile.role }}</h3>
          <ul class="detail-traits" aria-label="性格标签">
            <li v-for="trait in detail.profile.personality" :key="trait">
              {{ trait }}
            </li>
          </ul>
          <p class="world-context">
            Day {{ detail.world_context.day }} · {{ detail.world_context.time }} ·
            {{ detail.world_context.time_phase }}
          </p>
        </section>

        <section class="current-state" aria-labelledby="current-state-heading">
          <p class="detail-label">Current state</p>
          <h3 id="current-state-heading">当前状态</h3>
          <dl class="state-facts">
            <div>
              <dt>所在地点</dt>
              <dd>{{ detail.state.location_name }}</dd>
            </div>
            <div>
              <dt>当前行动</dt>
              <dd>{{ actionLabels[detail.state.current_action] }}</dd>
            </div>
          </dl>

          <dl class="detail-needs">
            <div v-for="(label, need) in needLabels" :key="need" class="detail-need-row">
              <dt>{{ label }}</dt>
              <dd>
                <progress :value="detail.state.status[need]" max="100">
                  {{ detail.state.status[need] }} / 100
                </progress>
                <span>{{ detail.state.status[need] }}</span>
              </dd>
            </div>
          </dl>
        </section>

        <section class="recent-history" aria-labelledby="recent-actions-heading">
          <p class="detail-label">Action history</p>
          <h3 id="recent-actions-heading">最近行动</h3>
          <p v-if="detail.recent_actions.length === 0" class="empty-history">
            还没有已记录的行动。
          </p>
          <ol v-else class="action-history" aria-label="最近行动">
            <li v-for="action in detail.recent_actions" :key="action.id">
              <p class="action-time">第 {{ action.clock_tick }} 回合 · {{ action.world_time }}</p>
              <h4>{{ actionLabels[action.action_type] }}<template v-if="action.target_name"> → {{ action.target_name }}</template></h4>
              <p>{{ action.reason_text }}</p>
            </li>
          </ol>
        </section>

        <section
          class="memory-explanations"
          aria-labelledby="memory-explanations-heading"
        >
          <p class="detail-label">Memory</p>
          <h3 id="memory-explanations-heading">
            <button
              type="button"
              class="memory-toggle"
              :aria-expanded="memoryExpanded"
              aria-controls="npc-memory-explanations"
              @click="memoryExpanded = !memoryExpanded"
            >
              <span>相关记忆</span>
              <span class="memory-status">{{ memoryStatus }}</span>
            </button>
          </h3>

          <!-- The region stays mounted so the toggle's aria-controls always
               resolves; collapsing removes the body, not the target. -->
          <div id="npc-memory-explanations">
            <template v-if="memoryExpanded">
              <p
                v-if="memoryState === 'loading'"
                class="memory-note"
                role="status"
                aria-live="polite"
              >
                正在读取这位居民的相关记忆…
              </p>

              <div
                v-else-if="memoryState === 'failed'"
                class="detail-error"
                role="alert"
              >
                <p>{{ memoryFailure }}</p>
                <button type="button" @click="$emit('retry-memory')">重新读取</button>
              </div>

              <p v-else-if="memoryState === 'unread'" class="memory-note">
                还没有读取这位居民的相关记忆。
              </p>

              <template v-else>
                <p v-if="memory?.fallback_used" class="memory-note">
                  当前以关键词匹配作为降级方式检索，结果可能不如平时贴切。
                </p>
                <p v-if="memoryState === 'empty'" class="memory-note">
                  这位居民暂时没有可以公开说明的记忆。
                </p>
                <ol v-else class="memory-list" aria-label="相关记忆">
                  <li v-for="item in memoryItems" :key="item.id">
                    <p class="memory-meta">
                      <span class="memory-source">{{ item.source.label }}</span>
                      · 第 {{ item.occurred_clock_tick }} 回合
                    </p>
                    <p class="memory-summary">{{ item.summary }}</p>
                    <p class="memory-reason">{{ item.reason_text }}</p>
                  </li>
                </ol>
              </template>
            </template>
          </div>
        </section>
      </div>

      <div
        v-if="activeTab === 'thought'"
        id="npc-panel-thought"
        class="detail-thought"
        role="tabpanel"
        aria-labelledby="npc-tab-thought"
      >
        <NpcThoughtTab
          :npc-id="selectedNpcId"
          :clock-tick="detail?.world_context.clock_tick ?? null"
        />
      </div>
    </template>
  </aside>
</template>

<style scoped>
.npc-detail-panel {
  margin-top: 3rem;
  padding: 1.5rem;
  border: 1px solid #aebbac;
  border-left: 0.35rem solid #315b45;
  border-radius: 0.9rem;
  background: rgb(252 252 247 / 94%);
  box-shadow: 0 1rem 2.5rem rgb(50 66 53 / 10%);
}

.detail-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid #c4cbc0;
}

.detail-header h2,
.detail-content h3,
.action-history h4 {
  color: #1f3d2a;
}

.detail-header h2 {
  margin: 0.3rem 0 0;
  font-family: Georgia, "Times New Roman", serif;
  font-size: clamp(1.8rem, 4vw, 2.5rem);
  font-weight: 500;
}

.detail-label {
  margin: 0;
  color: #586b5d;
  font-size: 0.72rem;
  font-weight: 750;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.detail-close {
  padding: 0.55rem 0.75rem;
  border: 1px solid #9eaea0;
  color: #315b45;
  background: transparent;
}

.detail-close:hover {
  color: #fff;
  background: #315b45;
}

.detail-status,
.detail-error {
  margin: 1rem 0 0;
  padding: 0.9rem 1rem;
  border-radius: 0.65rem;
  background: #edf0e8;
}

.detail-status {
  color: #536057;
}

.detail-error {
  border: 1px solid #b36f61;
  color: #7d392f;
  background: #f7ece8;
}

.detail-error p {
  margin: 0 0 0.75rem;
}

.detail-tabs {
  display: flex;
  gap: 0.3rem;
  margin-top: 1.1rem;
  padding-bottom: 0.55rem;
  border-bottom: 1px solid #c4cbc0;
}

.detail-tabs button {
  padding: 0.5rem 1.1rem;
  border: 1px solid transparent;
  border-radius: 999px;
  color: #4b5b50;
  background: transparent;
  font-size: 0.95rem;
  font-weight: 650;
}

.detail-tabs button:hover {
  color: #1f3d2a;
  background: #edf0e8;
}

.detail-tabs button[aria-selected="true"] {
  color: #f4f7f1;
  background: #315b45;
}

.detail-content {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1.5rem;
  margin-top: 1.5rem;
}

.detail-thought {
  margin-top: 1.5rem;
}

.detail-content h3 {
  margin: 0.3rem 0 0.8rem;
}

.detail-traits {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin: 0;
  padding: 0;
  list-style: none;
}

.detail-traits li {
  padding: 0.3rem 0.55rem;
  border-radius: 999px;
  color: #3d5143;
  background: #e6eadf;
  font-size: 0.78rem;
}

.world-context {
  margin: 1.1rem 0 0;
  color: #536057;
  font-variant-numeric: tabular-nums;
}

.state-facts,
.detail-needs {
  margin: 0;
}

.state-facts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
}

.state-facts div {
  padding: 0.75rem;
  border-radius: 0.6rem;
  background: #edf0e8;
}

.state-facts dt,
.detail-need-row dt {
  color: #59645c;
  font-size: 0.78rem;
}

.state-facts dd {
  margin: 0.25rem 0 0;
  color: #253027;
  font-weight: 650;
}

.detail-needs {
  display: grid;
  gap: 0.55rem;
  margin-top: 1rem;
}

.detail-need-row {
  display: grid;
  grid-template-columns: 3.5rem minmax(0, 1fr);
  align-items: center;
  gap: 0.65rem;
}

.detail-need-row dd {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 2rem;
  align-items: center;
  gap: 0.5rem;
  margin: 0;
  font-size: 0.78rem;
  font-variant-numeric: tabular-nums;
}

.recent-history,
.memory-explanations {
  grid-column: 1 / -1;
  padding-top: 1.25rem;
  border-top: 1px solid #c4cbc0;
}

.empty-history {
  margin: 0;
  color: #59645c;
}

.action-history {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.75rem;
  margin: 0;
  padding: 0;
  list-style: none;
}

.action-history li {
  padding: 0.9rem;
  border: 1px solid #cbd1c6;
  border-radius: 0.65rem;
  background: #f4f5ef;
}

.action-history h4 {
  margin: 0.3rem 0 0.45rem;
  font-size: 1rem;
}

.action-history li > p:last-child {
  margin: 0;
  color: #4b5b50;
  line-height: 1.55;
}

.action-time {
  margin: 0;
  color: #7a6348;
  font-size: 0.75rem;
  font-variant-numeric: tabular-nums;
}

.memory-explanations h3 {
  margin: 0.3rem 0 0;
  font-weight: inherit;
}

.memory-toggle {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.75rem;
  width: 100%;
  padding: 0.6rem 0.75rem;
  border: 1px solid #9eaea0;
  color: #1f3d2a;
  background: #edf0e8;
  font-size: 1rem;
  text-align: left;
}

.memory-toggle:hover {
  color: #fff;
  background: #315b45;
}

.memory-status {
  color: inherit;
  font-size: 0.78rem;
  opacity: 0.85;
}

.memory-note {
  margin: 0.75rem 0 0;
  color: #59645c;
}

.memory-explanations .detail-error {
  margin-top: 0.75rem;
}

.memory-list {
  display: grid;
  gap: 0.75rem;
  margin: 0.75rem 0 0;
  padding: 0;
  list-style: none;
}

.memory-list li {
  padding: 0.9rem;
  border: 1px solid #cbd1c6;
  border-radius: 0.65rem;
  background: #f4f5ef;
}

.memory-meta {
  margin: 0;
  color: #7a6348;
  font-size: 0.75rem;
  font-variant-numeric: tabular-nums;
}

.memory-source {
  font-weight: 700;
}

.memory-summary {
  margin: 0.35rem 0 0.4rem;
  color: #253027;
  line-height: 1.55;
}

.memory-reason {
  margin: 0;
  color: #4b5b50;
  font-size: 0.88rem;
  line-height: 1.5;
}

@media (max-width: 700px) {
  .npc-detail-panel {
    padding: 1.1rem;
  }

  .detail-content,
  .state-facts,
  .action-history {
    grid-template-columns: 1fr;
  }

  .recent-history,
  .memory-explanations {
    grid-column: auto;
  }
}
</style>
