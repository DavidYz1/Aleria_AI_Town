<script setup lang="ts">
import type { NpcInfo } from '../types/world'

defineProps<{
  npc: NpcInfo
  locationName: string
}>()

const emit = defineEmits<{
  select: [npcId: string]
}>()

const needLabels = {
  energy: 'Energy',
  mood: 'Mood',
  social: 'Social',
} as const
</script>

<template>
  <article class="card npc-card">
    <div class="npc-heading">
      <div>
        <p class="card-label">{{ npc.role }}</p>
        <h3>{{ npc.name }}</h3>
      </div>
      <span class="action-badge">{{ npc.current_action }}</span>
    </div>

    <p class="npc-location">所在地点：{{ locationName }}</p>

    <ul class="personality-list" aria-label="性格标签">
      <li v-for="trait in npc.personality" :key="trait">{{ trait }}</li>
    </ul>

    <dl class="needs-list">
      <div v-for="(label, need) in needLabels" :key="need" class="need-row">
        <dt>{{ label }}</dt>
        <dd>
          <progress :value="npc.status[need]" max="100">
            {{ npc.status[need] }} / 100
          </progress>
          <span>{{ npc.status[need] }}</span>
        </dd>
      </div>
    </dl>

    <button
      type="button"
      class="npc-detail-trigger"
      @click="emit('select', npc.id)"
    >
      查看详情
    </button>
  </article>
</template>

<style scoped>
.npc-detail-trigger {
  width: 100%;
  margin-top: 1.2rem;
}
</style>
