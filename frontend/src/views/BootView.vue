<script setup lang="ts">
defineProps<{
  hasProfile: boolean
}>()

defineEmits<{
  continue: []
}>()
</script>

<template>
  <main class="cinematic-shell" data-scene="boot">
    <section class="cinematic-card" aria-labelledby="boot-title">
      <p class="cinematic-kicker">Aleria AI Town</p>
      <h1 id="boot-title">曦谷</h1>
      <p class="cinematic-lede">
        雾气停在石墙与松林之间。你的故事正等待下一步。
      </p>
      <button type="button" data-action="continue" @click="$emit('continue')">
        {{ hasProfile ? '继续冒险' : '踏入曦谷' }}
      </button>
    </section>
  </main>
</template>
