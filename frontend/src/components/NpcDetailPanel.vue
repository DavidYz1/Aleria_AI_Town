<script setup lang="ts">
import type { NpcDetailData } from '../types/npc'

defineProps<{
  selectedNpcId: string | null
  detail: NpcDetailData | null
  loading: boolean
  error: string | null
}>()

defineEmits<{
  close: []
  retry: []
}>()

const actionLabels = {
  move: '移动',
  rest: '休息',
  work: '工作',
  eat: '用餐',
  social: '交谈',
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

    <div v-if="detail" class="detail-content">
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
            <p class="action-time">Tick {{ action.tick }} · {{ action.world_time }}</p>
            <h4>{{ actionLabels[action.action_type] }}<template v-if="action.target_name"> → {{ action.target_name }}</template></h4>
            <p>{{ action.reason_text }}</p>
          </li>
        </ol>
      </section>
    </div>
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

.detail-content {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1.5rem;
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

.recent-history {
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

@media (max-width: 700px) {
  .npc-detail-panel {
    padding: 1.1rem;
  }

  .detail-content,
  .state-facts,
  .action-history {
    grid-template-columns: 1fr;
  }

  .recent-history {
    grid-column: auto;
  }
}
</style>
