<script setup lang="ts">
import type {
  QuestData,
  QuestInteraction,
  QuestStatus,
} from '../types/playerQuest'


defineProps<{
  quest: QuestData
  mutating: boolean
  mutationError: string | null
}>()

defineEmits<{
  interact: [interaction: QuestInteraction]
}>()

const statusLabels: Record<QuestStatus, string> = {
  available: '可接受',
  accepted: '已接受',
  briefed_by_grey: '已获线索',
  shoe_found: '发现鞋子',
  child_found: '找到孩子',
  completed: '已完成',
}
</script>

<template>
  <section class="card quest-panel" aria-labelledby="quest-heading">
    <div class="quest-heading">
      <div>
        <p class="card-label">当前任务</p>
        <h3 id="quest-heading">{{ quest.title }}</h3>
      </div>
      <span class="quest-status">{{ statusLabels[quest.status] }}</span>
    </div>

    <p class="quest-objective">{{ quest.objective }}</p>

    <p v-if="mutating" class="panel-status" role="status" aria-live="polite">
      正在更新任务…
    </p>
    <p v-if="mutationError" class="panel-alert" role="alert">
      {{ mutationError }}
    </p>

    <div v-if="quest.available_interactions.length > 0" class="quest-actions">
      <button
        v-for="interaction in quest.available_interactions"
        :key="interaction.id"
        type="button"
        :disabled="mutating"
        @click="$emit('interact', interaction.id)"
      >
        {{ interaction.label }}
      </button>
    </div>
    <p v-else-if="quest.status === 'completed'" class="quest-complete">
      任务已经完成，孩子安全回到了星辉酒馆；鞋边的印记仍没有答案。
    </p>

    <div v-if="quest.recent_events.length > 0" class="quest-history">
      <h4>最近进展</h4>
      <ol>
        <li v-for="event in quest.recent_events" :key="event.id">
          {{ event.description }}
        </li>
      </ol>
    </div>
  </section>
</template>

<style scoped>
.quest-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.quest-heading h3 {
  margin-bottom: 0;
}

.quest-status {
  flex: none;
  padding: 0.3rem 0.65rem;
  border-radius: 999px;
  background: #e6eadf;
  color: #3d5143;
  font-size: 0.78rem;
  font-weight: 700;
}

.quest-objective {
  margin: 1rem 0;
  color: #33483a;
  line-height: 1.65;
}

.panel-status,
.panel-alert,
.quest-complete {
  padding: 0.75rem;
  border-radius: 0.55rem;
}

.panel-status {
  background: #edf1e9;
}

.panel-alert {
  border: 1px solid #b36f61;
  color: #713d35;
}

.quest-complete {
  background: #e2eee3;
  color: #2f5c39;
}

.quest-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
}

.quest-history {
  margin-top: 1.2rem;
  padding-top: 1rem;
  border-top: 1px solid #d8ddd4;
}

.quest-history h4 {
  margin: 0 0 0.6rem;
  color: #3d5143;
  font-size: 0.9rem;
}

.quest-history ol {
  display: grid;
  gap: 0.45rem;
  margin: 0;
  padding-left: 1.25rem;
  color: #59645c;
  line-height: 1.5;
}
</style>
