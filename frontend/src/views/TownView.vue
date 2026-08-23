<script setup lang="ts">
import { computed, onMounted } from 'vue'

import LocationCard from '../components/LocationCard.vue'
import NpcCard from '../components/NpcCard.vue'
import { useWorldStore } from '../stores/world'

const store = useWorldStore()

const locationNames = computed(
  () => new Map(store.data?.locations.map((location) => [location.id, location.name]) ?? []),
)

function reloadWorld(): void {
  void store.loadWorld()
}

onMounted(reloadWorld)
</script>

<template>
  <main class="town-shell">
    <header class="town-header">
      <p class="eyebrow">Aleria AI Town</p>
      <h1>{{ store.data?.world.name ?? '晨曦镇' }}</h1>
      <p v-if="store.data" class="world-time">
        Day {{ store.data.world.day }} · {{ store.data.world.time }}
      </p>
    </header>

    <section v-if="store.loading" class="state-panel" role="status" aria-live="polite">
      正在读取晨曦镇…
    </section>

    <section v-else-if="store.error" class="state-panel error-panel" role="alert">
      <p>{{ store.error }}</p>
      <button type="button" @click="reloadWorld">重新加载</button>
    </section>

    <section v-else-if="store.isEmpty" class="state-panel" role="status">
      世界数据尚未准备完成。
    </section>

    <template v-else-if="store.data">
      <section class="town-section" aria-labelledby="locations-heading">
        <div class="section-heading">
          <p class="section-number">02</p>
          <h2 id="locations-heading">城镇地点</h2>
        </div>
        <div class="location-grid">
          <LocationCard
            v-for="location in store.data.locations"
            :key="location.id"
            :location="location"
          />
        </div>
      </section>

      <section class="town-section" aria-labelledby="npcs-heading">
        <div class="section-heading">
          <p class="section-number">03</p>
          <h2 id="npcs-heading">居民状态</h2>
        </div>
        <div class="npc-grid">
          <NpcCard
            v-for="npc in store.data.npcs"
            :key="npc.id"
            :npc="npc"
            :location-name="locationNames.get(npc.location_id) ?? '未知地点'"
          />
        </div>
      </section>
    </template>
  </main>
</template>
