<script setup lang="ts">
import type { PlayerData } from '../types/playerQuest'


defineProps<{
  player: PlayerData | null
  loading: boolean
  error: string | null
}>()

defineEmits<{
  retry: []
}>()
</script>

<template>
  <section class="card player-location-panel" aria-labelledby="player-location-heading">
    <p class="card-label">玩家位置</p>
    <h2 id="player-location-heading">旅行者</h2>
    <p class="player-hook">失去记忆，只留下一个无法解释的印记。</p>

    <p v-if="loading" class="panel-status" role="status" aria-live="polite">
      {{ player === null ? '正在读取玩家位置…' : '正在刷新玩家位置…' }}
    </p>

    <div v-if="error" class="panel-alert" role="alert">
      <p>{{ error }}</p>
      <button type="button" @click="$emit('retry')">重新加载</button>
    </div>

    <div v-if="player" class="player-location-data">
      <p>当前位置</p>
      <h3>{{ player.location_name }}</h3>
    </div>
  </section>
</template>

<style scoped>
.player-location-panel h2 {
  margin: 0.35rem 0 1rem;
  color: #1f3d2a;
  font-size: 1.15rem;
}

.player-hook {
  margin: -0.45rem 0 1rem;
  font-size: 0.86rem;
  line-height: 1.5;
}

.player-hook,
.panel-status,
.panel-alert,
.player-location-data p {
  color: #59645c;
}

.panel-alert {
  padding: 0.9rem;
  border: 1px solid #b36f61;
  border-radius: 0.6rem;
}

.panel-alert p {
  margin-top: 0;
}

.player-location-data {
  padding-top: 0.75rem;
  border-top: 1px solid #d8ddd4;
}

.player-location-data p {
  margin: 0;
  font-size: 0.82rem;
}

.player-location-data h3 {
  margin-bottom: 0;
}
</style>
