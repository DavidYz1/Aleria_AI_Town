<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'

import LocationCard from '../components/LocationCard.vue'
import NpcCard from '../components/NpcCard.vue'
import NpcChatPanel from '../components/NpcChatPanel.vue'
import NpcDetailPanel from '../components/NpcDetailPanel.vue'
import PlayerLocationPanel from '../components/PlayerLocationPanel.vue'
import QuestPanel from '../components/QuestPanel.vue'
import TickPanel from '../components/TickPanel.vue'
import { useNpcChatStore } from '../stores/npcChat'
import { useNpcDetailStore } from '../stores/npcDetail'
import { usePlayerProfileStore } from '../stores/playerProfile'
import { usePlayerQuestStore } from '../stores/playerQuest'
import { useWorldStore } from '../stores/world'
import type { QuestInteraction } from '../types/playerQuest'

const store = useWorldStore()
const npcDetailStore = useNpcDetailStore()
const npcChatStore = useNpcChatStore()
const playerProfileStore = usePlayerProfileStore()
const playerQuestStore = usePlayerQuestStore()

const locationNames = computed(
  () => new Map(store.data?.locations.map((location) => [location.id, location.name]) ?? []),
)
const selectedNpcName = computed(() => {
  const npcId = npcDetailStore.selectedNpcId
  if (npcId === null) return ''
  return store.data?.npcs.find((npc) => npc.id === npcId)?.name ?? npcId
})
const selectedChatSession = computed(() => {
  const npcId = npcDetailStore.selectedNpcId
  return npcId === null ? null : npcChatStore.sessionFor(npcId)
})

function reloadWorld(): void {
  void store.loadWorld()
}

function loadTown(): void {
  void Promise.all([
    store.loadWorld(),
    playerQuestStore.load(),
  ])
}

function retryPlayerQuest(): void {
  void playerQuestStore.retry()
}

function travelPlayer(locationId: string): void {
  void playerQuestStore.travel(locationId)
}

function interactWithQuest(interaction: QuestInteraction): void {
  void playerQuestStore.interact(interaction)
}

function advanceWorld(): void {
  void store.advanceTick()
}

function selectNpc(npcId: string): void {
  void npcDetailStore.selectNpc(npcId)
}

function retryNpcDetail(): void {
  void npcDetailStore.retry()
}

function updatePendingMessage(value: string): void {
  const npcId = npcDetailStore.selectedNpcId
  if (npcId !== null) npcChatStore.setPendingMessage(npcId, value)
}

function sendChatMessage(): void {
  const npcId = npcDetailStore.selectedNpcId
  if (npcId !== null) void npcChatStore.send(npcId, playerProfileStore.profile)
}

function retryChatMessage(): void {
  const npcId = npcDetailStore.selectedNpcId
  if (npcId !== null) void npcChatStore.retry(npcId, playerProfileStore.profile)
}

watch(
  () => store.data?.world.tick,
  (nextTick, previousTick) => {
    if (
      nextTick !== undefined
      && previousTick !== undefined
      && nextTick !== previousTick
      && npcDetailStore.selectedNpcId !== null
    ) {
      void npcDetailStore.refresh()
    }
  },
)

onMounted(loadTown)
</script>

<template>
  <main class="town-shell">
    <header class="town-header">
      <p class="eyebrow">Aleria AI Town</p>
      <h1>{{ store.data?.world.name ?? '曦谷' }}</h1>
      <p v-if="store.data" class="world-time">
        Day {{ store.data.world.day }} · {{ store.data.world.time }}
      </p>
    </header>

    <section v-if="store.loading" class="state-panel" role="status" aria-live="polite">
      正在读取曦谷…
    </section>

    <section v-else-if="store.error" class="state-panel error-panel" role="alert">
      <p>{{ store.error }}</p>
      <button type="button" @click="reloadWorld">重新加载</button>
    </section>

    <section v-else-if="store.isEmpty" class="state-panel" role="status">
      世界数据尚未准备完成。
    </section>

    <template v-else-if="store.data">
      <TickPanel
        :advancing="store.advancing"
        :error="store.tickError"
        :tick="store.lastTick"
        @advance="advanceWorld"
      />

      <section class="town-section" aria-labelledby="journey-heading">
        <div class="section-heading">
          <p class="section-number">02</p>
          <h2 id="journey-heading">旅行与委托</h2>
        </div>
        <div class="player-quest-layout">
          <PlayerLocationPanel
            :player="playerQuestStore.data?.player ?? null"
            :loading="playerQuestStore.loading"
            :error="playerQuestStore.error"
            @retry="retryPlayerQuest"
          />
          <QuestPanel
            v-if="playerQuestStore.data"
            :quest="playerQuestStore.data.quest"
            :mutating="playerQuestStore.mutating"
            :mutation-error="playerQuestStore.mutationError"
            @interact="interactWithQuest"
          />
        </div>
      </section>

      <section class="town-section" aria-labelledby="locations-heading">
        <div class="section-heading">
          <p class="section-number">03</p>
          <h2 id="locations-heading">城镇地点</h2>
        </div>
        <div class="location-grid">
          <LocationCard
            v-for="location in store.data.locations"
            :key="location.id"
            :location="location"
            :is-current="playerQuestStore.data?.player.location_id === location.id"
            :travelling="playerQuestStore.mutating"
            @travel="travelPlayer"
          />
        </div>
      </section>

      <section class="town-section" aria-labelledby="npcs-heading">
        <div class="section-heading">
          <p class="section-number">04</p>
          <h2 id="npcs-heading">居民状态</h2>
        </div>
        <div
          class="resident-layout"
          :class="{ 'has-detail': npcDetailStore.selectedNpcId !== null }"
        >
          <div class="npc-grid">
            <NpcCard
              v-for="npc in store.data.npcs"
              :key="npc.id"
              :npc="npc"
              :location-name="locationNames.get(npc.location_id) ?? '未知地点'"
              @select="selectNpc"
            />
          </div>

          <div
            v-if="npcDetailStore.selectedNpcId !== null && selectedChatSession"
            class="detail-chat-stack"
          >
            <NpcDetailPanel
              :selected-npc-id="npcDetailStore.selectedNpcId"
              :detail="npcDetailStore.data"
              :loading="npcDetailStore.loading"
              :error="npcDetailStore.error"
              @close="npcDetailStore.close"
              @retry="retryNpcDetail"
            />
            <NpcChatPanel
              :selected-npc-id="npcDetailStore.selectedNpcId"
              :npc-name="selectedNpcName"
              :messages="selectedChatSession.messages"
              :sending="selectedChatSession.sending"
              :error="selectedChatSession.error"
              :pending-message="selectedChatSession.pendingMessage"
              :provider="selectedChatSession.provider"
              :fallback-used="selectedChatSession.fallbackUsed"
              @update:pending-message="updatePendingMessage"
              @send="sendChatMessage"
              @retry="retryChatMessage"
            />
          </div>
        </div>
      </section>
    </template>
  </main>
</template>

<style scoped>
.resident-layout.has-detail {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(18rem, 0.9fr);
  align-items: start;
  gap: 1rem;
}

.resident-layout.has-detail .npc-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.resident-layout :deep(.npc-detail-panel) {
  margin-top: 0;
}

.detail-chat-stack {
  display: grid;
  gap: 1rem;
}

@media (max-width: 900px) {
  .resident-layout.has-detail {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .resident-layout.has-detail .npc-grid {
    grid-template-columns: 1fr;
  }
}
</style>
