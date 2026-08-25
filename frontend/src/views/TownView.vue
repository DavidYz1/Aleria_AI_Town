<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import LocationCard from '../components/LocationCard.vue'
import NpcCard from '../components/NpcCard.vue'
import NpcChatPanel from '../components/NpcChatPanel.vue'
import NpcDetailPanel from '../components/NpcDetailPanel.vue'
import PlayerLocationPanel from '../components/PlayerLocationPanel.vue'
import QuestPanel from '../components/QuestPanel.vue'
import TickPanel from '../components/TickPanel.vue'
import TownGameHost from '../components/TownGameHost.vue'
import { projectNpcs } from '../game/npcProjection'
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
const townGameHost = ref<InstanceType<typeof TownGameHost> | null>(null)
const pendingEnteredLocationId = ref<string | null>(null)
let syncingEnteredLocation = false
let quickTravelRequests = 0

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
const projectedNpcs = computed(() => projectNpcs(store.data?.npcs ?? []))
const adventurerClassTitle = computed(() => ({
  mage: '法师',
  ranger: '游侠',
  cleric: '牧师',
})[playerProfileStore.profile?.adventurerClass ?? 'ranger'])
const displayedPlayer = computed(() => playerQuestStore.data?.player ?? null)

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

async function travelPlayer(locationId: string): Promise<void> {
  quickTravelRequests += 1
  try {
    const travelled = await playerQuestStore.travel(locationId)
    if (
      travelled
      && playerQuestStore.data?.player.location_id === locationId
    ) {
      pendingEnteredLocationId.value = null
      townGameHost.value?.teleportPlayer(locationId)
    }
  } finally {
    quickTravelRequests -= 1
  }
  if (pendingEnteredLocationId.value !== null) {
    void syncEnteredPlayerLocation()
  }
}

async function syncEnteredPlayerLocation(): Promise<void> {
  if (
    syncingEnteredLocation
    || quickTravelRequests > 0
    || playerQuestStore.mutating
  ) return
  const locationId = pendingEnteredLocationId.value
  if (locationId === null) return
  if (playerQuestStore.data?.player.location_id === locationId) {
    pendingEnteredLocationId.value = null
    return
  }

  syncingEnteredLocation = true
  try {
    await playerQuestStore.travel(locationId)
  } finally {
    syncingEnteredLocation = false
    if (pendingEnteredLocationId.value === locationId) {
      pendingEnteredLocationId.value = null
    }
  }
  if (pendingEnteredLocationId.value !== null) {
    void syncEnteredPlayerLocation()
  }
}

function enterPlayerLocation(locationId: string): void {
  pendingEnteredLocationId.value = locationId
  void syncEnteredPlayerLocation()
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
  () => playerQuestStore.mutating,
  (mutating) => {
    if (!mutating) void syncEnteredPlayerLocation()
  },
)

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
      <section
        v-if="playerProfileStore.profile"
        class="town-section town-map-section"
        aria-labelledby="town-map-heading"
      >
        <div class="section-heading">
          <p class="section-number">地图探索</p>
          <h2 id="town-map-heading">曦谷全景</h2>
        </div>
        <div class="town-play-layout">
          <div class="town-game-host-column">
            <TownGameHost
              ref="townGameHost"
              :profile="playerProfileStore.profile"
              :player-location-id="playerQuestStore.data?.player.location_id ?? null"
              :npcs="projectedNpcs"
              @npc-selected="selectNpc"
              @player-location-entered="enterPlayerLocation"
            />
          </div>

          <aside class="town-map-hud" aria-label="冒险者与居民信息">
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
            <div v-else class="card map-help-card">
              <p class="card-label">当前冒险者</p>
              <h3>{{ playerProfileStore.profile.displayName }} · {{ adventurerClassTitle }}</h3>
              <p>点击地图后使用 WASD 或方向键移动，点击居民可查看状态并开始交流。</p>
              <p class="map-boundary-note">
                地图坐标只用于画面表现；城镇地点、居民状态与任务仍由 Backend 决定。
              </p>
            </div>
          </aside>
        </div>
      </section>

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
            :player="displayedPlayer"
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
        <div class="resident-layout">
          <div class="npc-grid">
            <NpcCard
              v-for="npc in store.data.npcs"
              :key="npc.id"
              :npc="npc"
              :location-name="locationNames.get(npc.location_id) ?? '未知地点'"
              @select="selectNpc"
            />
          </div>
        </div>
      </section>
    </template>
  </main>
</template>

<style scoped>
.town-map-section {
  margin-top: 2rem;
}

.town-play-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.75fr) minmax(17rem, 0.75fr);
  align-items: start;
  gap: 1rem;
}

.town-game-host-column {
  min-width: 0;
}

.town-map-hud {
  min-width: 0;
}

.detail-chat-stack {
  display: grid;
  gap: 1rem;
}

.detail-chat-stack :deep(.npc-detail-panel) {
  margin-top: 0;
}

.map-help-card h3 {
  margin-bottom: 0.75rem;
}

.map-boundary-note {
  padding-top: 0.75rem;
  border-top: 1px solid #d7ddd3;
  font-size: 0.88rem;
}

@media (max-width: 900px) {
  .town-play-layout {
    grid-template-columns: 1fr;
  }
}
</style>
