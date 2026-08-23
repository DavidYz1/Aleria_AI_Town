<script setup lang="ts">
import type { LocationInfo } from '../types/world'

defineProps<{
  location: LocationInfo
}>()
</script>

<template>
  <article class="card location-card">
    <p class="card-label">地点</p>
    <h3>{{ location.name }}</h3>
    <p>{{ location.description }}</p>
  </article>
</template>
