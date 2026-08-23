<script setup lang="ts">
import { computed } from 'vue'

import type { WorldActionInfo, WorldTickData } from '../types/worldTick'

const props = defineProps<{
  advancing: boolean
  error: string | null
  tick: WorldTickData | null
}>()

defineEmits<{ advance: [] }>()

const actionLabels = {
  move: '移动',
  rest: '休息',
  work: '工作',
  eat: '用餐',
  social: '交谈',
} as const

const npcNames = computed(
  () => new Map(props.tick?.world.npcs.map((npc) => [npc.id, npc.name]) ?? []),
)
const locationNames = computed(
  () => new Map(props.tick?.world.locations.map((location) => [location.id, location.name]) ?? []),
)

function actionText(action: WorldActionInfo): string {
  const actor = npcNames.value.get(action.actor_id) ?? action.actor_id
  let target = ''
  if (action.target_kind === 'location' && action.target_id) {
    target = ` → ${locationNames.value.get(action.target_id) ?? action.target_id}`
  } else if (action.target_kind === 'npc' && action.target_id) {
    target = ` → ${npcNames.value.get(action.target_id) ?? action.target_id}`
  }
  return `${actor} · ${actionLabels[action.action_type]}${target}`
}
</script>

<template>
  <section class="tick-panel" aria-labelledby="tick-heading">
    <div class="tick-control">
      <div>
        <p class="section-number">01</p>
        <h2 id="tick-heading">世界推进</h2>
        <p>每次推进一小时，三名居民会从同一世界快照做出行动。</p>
      </div>
      <button type="button" :disabled="advancing" @click="$emit('advance')">
        {{ advancing ? '推进中…' : '推进 1 小时' }}
      </button>
    </div>

    <p v-if="error" class="tick-error" role="alert">{{ error }}</p>

    <div v-if="tick" class="tick-result" aria-live="polite">
      <h3>Tick {{ tick.world.world.tick }} · {{ tick.world.world.time }}</h3>
      <div class="tick-columns">
        <div>
          <h4>NPC Actions</h4>
          <ul>
            <li v-for="action in tick.actions" :key="action.id">
              {{ actionText(action) }}
            </li>
          </ul>
        </div>
        <div>
          <h4>World Events</h4>
          <ul>
            <li v-for="event in tick.events" :key="event.id">
              {{ event.description }}
            </li>
          </ul>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.tick-panel {
  margin-top: 2rem;
  padding: 1.35rem;
  border: 1px solid #b9c2b7;
  border-radius: 0.8rem;
  background: rgb(255 255 255 / 68%);
}

.tick-control {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1.5rem;
}

.tick-control h2,
.tick-result h3,
.tick-result h4 {
  margin: 0.25rem 0;
  color: #1f3d2a;
}

.tick-control p:last-child {
  margin: 0.4rem 0 0;
  color: #59645c;
}

button:disabled {
  opacity: 0.65;
  cursor: wait;
}

.tick-error {
  margin: 1rem 0 0;
  color: #8a3f34;
}

.tick-result {
  margin-top: 1.25rem;
  padding-top: 1rem;
  border-top: 1px solid #c4cbc0;
}

.tick-columns {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}

ul {
  display: grid;
  gap: 0.45rem;
  margin: 0.65rem 0 0;
  padding-left: 1.2rem;
  color: #4b5b50;
}

@media (max-width: 640px) {
  .tick-control {
    align-items: stretch;
    flex-direction: column;
  }

  .tick-columns {
    grid-template-columns: 1fr;
  }
}
</style>
