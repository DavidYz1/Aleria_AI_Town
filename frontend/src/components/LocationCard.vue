<script setup lang="ts">
import type { LocationInfo } from '../types/world'

const props = defineProps<{
  location: LocationInfo
  isCurrent: boolean
  travelling: boolean
}>()

const emit = defineEmits<{
  travel: [locationId: string]
}>()

function travel(): void {
  if (!props.isCurrent && !props.travelling) {
    emit('travel', props.location.id)
  }
}
</script>

<template>
  <article
    class="card location-card"
    :class="{ 'is-current': isCurrent }"
    :aria-current="isCurrent ? 'location' : undefined"
  >
    <p class="card-label">地点</p>
    <h3>{{ location.name }}</h3>
    <p>{{ location.description }}</p>
    <button
      type="button"
      :disabled="isCurrent || travelling"
      @click="travel"
    >
      {{ isCurrent ? '当前位置' : travelling ? '旅行中…' : '快速前往' }}
    </button>
  </article>
</template>
