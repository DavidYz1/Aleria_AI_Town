<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { resetDemo } from '../api/demo'
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
import { useNpcMemoryStore } from '../stores/npcMemory'
import { usePlayerProfileStore } from '../stores/playerProfile'
import { usePlayerQuestStore } from '../stores/playerQuest'
import { useWorldStore } from '../stores/world'
import type { QuestInteraction } from '../types/playerQuest'

const emit = defineEmits<{
  restart: []
}>()

const store = useWorldStore()
const npcDetailStore = useNpcDetailStore()
const npcMemoryStore = useNpcMemoryStore()
const npcChatStore = useNpcChatStore()
const playerProfileStore = usePlayerProfileStore()
const playerQuestStore = usePlayerQuestStore()
const townGameHost = ref<InstanceType<typeof TownGameHost> | null>(null)
const pendingEnteredLocationId = ref<string | null>(null)
let syncingEnteredLocation = false
let quickTravelRequests = 0
const resettingDemo = ref(false)
const demoResetError = ref<string | null>(null)

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
const demoResetBlocked = computed(() => (
  store.advancing
  || playerQuestStore.mutating
  || Object.values(npcChatStore.sessionsByNpc).some((session) => session.sending)
))

function reloadWorld(): void {
  void store.loadWorld()
}

function retryWorldRefresh(): void {
  void store.retryRefresh()
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
  if (resettingDemo.value || !store.canMutate) return
  const expectedWorldVersion = store.data?.world.world_version
  if (expectedWorldVersion === undefined) return
  quickTravelRequests += 1
  try {
    const travelled = await playerQuestStore.travel(
      locationId,
      expectedWorldVersion,
      undefined,
      () => store.refreshWorld(),
    )
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
    || resettingDemo.value
    || quickTravelRequests > 0
    || playerQuestStore.mutating
    || !store.canMutate
  ) return
  const locationId = pendingEnteredLocationId.value
  if (locationId === null) return
  if (playerQuestStore.data?.player.location_id === locationId) {
    pendingEnteredLocationId.value = null
    return
  }

  syncingEnteredLocation = true
  try {
    const expectedWorldVersion = store.data?.world.world_version
    if (expectedWorldVersion !== undefined) {
      await playerQuestStore.travel(
        locationId,
        expectedWorldVersion,
        undefined,
        () => store.refreshWorld(),
      )
    }
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
  if (resettingDemo.value) return
  pendingEnteredLocationId.value = locationId
  void syncEnteredPlayerLocation()
}

function interactWithQuest(interaction: QuestInteraction): void {
  if (resettingDemo.value || !store.canMutate) return
  const expectedWorldVersion = store.data?.world.world_version
  if (expectedWorldVersion !== undefined) {
    void playerQuestStore.interact(
      interaction,
      expectedWorldVersion,
      undefined,
      () => store.refreshWorld(),
    )
  }
}

function advanceWorld(): void {
  if (resettingDemo.value || !store.canMutate) return
  void store.advanceTick()
}

function advanceWorldFromMap(): void {
  advanceWorld()
  // Clicking the overlay moves focus off the canvas; without this the player
  // would silently lose WASD movement after every shortcut tick.
  townGameHost.value?.focusCanvas()
}

async function restartAdventure(): Promise<void> {
  if (resettingDemo.value || demoResetBlocked.value) return
  const confirmed = window.confirm(
    '重新开始将清除当前世界进度、任务、事件、聊天记录和本地角色。是否继续？',
  )
  if (!confirmed) return

  resettingDemo.value = true
  demoResetError.value = null
  try {
    await resetDemo()
    pendingEnteredLocationId.value = null
    closeNpcDetail()
    npcChatStore.clearAll()
    store.reset()
    playerQuestStore.reset()
    emit('restart')
  } catch {
    demoResetError.value = '重新开始失败，当前世界没有改变，请稍后重试。'
  } finally {
    resettingDemo.value = false
  }
}

function selectNpc(npcId: string): void {
  // Two independent reads: a failed memory explanation must not hide the detail.
  void npcDetailStore.selectNpc(npcId)
  void npcMemoryStore.selectNpc(npcId)
}

function closeNpcDetail(): void {
  npcDetailStore.close()
  npcMemoryStore.close()
}

function retryNpcDetail(): void {
  void npcDetailStore.retry()
}

function retryNpcMemory(): void {
  void npcMemoryStore.retry()
}

function refreshSelectedNpcMemory(npcId: string): void {
  if (npcMemoryStore.selectedNpcId === npcId) void npcMemoryStore.refresh()
}

function updatePendingMessage(value: string): void {
  const npcId = npcDetailStore.selectedNpcId
  if (npcId !== null) npcChatStore.setPendingMessage(npcId, value)
}

async function deliverChatTurn(
  deliver: (npcId: string) => Promise<void>,
): Promise<void> {
  if (resettingDemo.value) return
  const npcId = npcDetailStore.selectedNpcId
  if (npcId === null) return
  const session = npcChatStore.sessionFor(npcId)
  const delivered = session.messages.length
  await deliver(npcId)
  // Only a landed turn can change what this NPC recalls.
  if (session.messages.length > delivered) refreshSelectedNpcMemory(npcId)
}

function sendChatMessage(): void {
  void deliverChatTurn(
    (npcId) => npcChatStore.send(npcId, playerProfileStore.profile),
  )
}

function retryChatMessage(): void {
  void deliverChatTurn(
    (npcId) => npcChatStore.retry(npcId, playerProfileStore.profile),
  )
}

watch(
  () => playerQuestStore.mutating,
  (mutating) => {
    if (!mutating) void syncEnteredPlayerLocation()
  },
)

watch(
  () => store.data?.world.world_version,
  (nextVersion, previousVersion) => {
    if (
      nextVersion === undefined
      || previousVersion === undefined
      || nextVersion === previousVersion
    ) return
    // Tick and Quest both move the authoritative version; each open panel makes
    // its own best-effort read so neither can block the other.
    if (npcDetailStore.selectedNpcId !== null) void npcDetailStore.refresh()
    if (npcMemoryStore.selectedNpcId !== null) void npcMemoryStore.refresh()
  },
)

onMounted(loadTown)
</script>

<template>
  <main class="town-shell">
    <header class="town-header">
      <div class="town-header-content">
        <div>
          <p class="eyebrow">Aleria AI Town</p>
          <h1>{{ store.data?.world.name ?? '曦谷' }}</h1>
          <p v-if="store.data" class="world-time">
            Day {{ store.data.world.day }} · {{ store.data.world.time }}
          </p>
        </div>
        <button
          class="demo-reset-button"
          data-action="restart-adventure"
          type="button"
          :disabled="resettingDemo || demoResetBlocked"
          @click="restartAdventure"
        >
          {{ resettingDemo ? '正在重置…' : '重新开始冒险' }}
        </button>
      </div>
      <p
        v-if="demoResetError"
        class="demo-reset-error"
        role="alert"
      >
        {{ demoResetError }}
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
      <section v-if="store.refreshError" class="state-panel error-panel world-refresh-error" role="alert">
        <p>{{ store.refreshError }}</p>
        <button type="button" :disabled="store.refreshing" @click="retryWorldRefresh">
          {{ store.refreshing ? '正在同步…' : '重新同步' }}
        </button>
      </section>

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
            <div class="town-game-stage">
              <TownGameHost
                ref="townGameHost"
                :profile="playerProfileStore.profile"
                :player-location-id="playerQuestStore.data?.player.location_id ?? null"
                :npcs="projectedNpcs"
                @npc-selected="selectNpc"
                @player-location-entered="enterPlayerLocation"
              />
              <button
                class="map-tick-button"
                data-action="advance-world-from-map"
                type="button"
                :disabled="store.advancing || resettingDemo"
                @click="advanceWorldFromMap"
              >
                {{ store.advancing ? '推进中…' : '推进 1 小时' }}
              </button>
            </div>

            <NpcChatPanel
              v-if="npcDetailStore.selectedNpcId !== null && selectedChatSession"
              :selected-npc-id="npcDetailStore.selectedNpcId"
              :npc-name="selectedNpcName"
              :messages="selectedChatSession.messages"
              :sending="selectedChatSession.sending || resettingDemo"
              :error="selectedChatSession.error"
              :pending-message="selectedChatSession.pendingMessage"
              :provider="selectedChatSession.provider"
              :fallback-used="selectedChatSession.fallbackUsed"
              @update:pending-message="updatePendingMessage"
              @send="sendChatMessage"
              @retry="retryChatMessage"
            />
          </div>

          <aside class="town-map-hud" aria-label="冒险者与居民信息">
            <NpcDetailPanel
              v-if="npcDetailStore.selectedNpcId !== null"
              :selected-npc-id="npcDetailStore.selectedNpcId"
              :detail="npcDetailStore.data"
              :loading="npcDetailStore.loading"
              :error="npcDetailStore.error"
              :memory="npcMemoryStore.data"
              :memory-loading="npcMemoryStore.loading"
              :memory-error="npcMemoryStore.error"
              @close="closeNpcDetail"
              @retry="retryNpcDetail"
              @retry-memory="retryNpcMemory"
            />
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
        :advancing="store.advancing || resettingDemo"
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
            :mutating="playerQuestStore.mutating || resettingDemo"
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
            :travelling="playerQuestStore.mutating || resettingDemo"
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

.town-header-content {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 2rem;
}

.demo-reset-button {
  flex: 0 0 auto;
  border: 1px solid #9b5d51;
  color: #7a3f35;
  background: rgb(255 250 245 / 82%);
}

.demo-reset-button:hover {
  color: #fff;
  background: #9b5d51;
}

.demo-reset-error {
  margin: 1rem 0 0;
  color: #8a453a;
}

.town-play-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.75fr) minmax(17rem, 0.75fr);
  align-items: start;
  gap: 1rem;
}

.town-game-host-column {
  display: grid;
  gap: 1rem;
  min-width: 0;
}

.town-game-stage {
  position: relative;
}

.map-tick-button {
  position: absolute;
  z-index: 3;
  inset: 0.85rem 0.85rem auto auto;
  padding: 0.5rem 0.85rem;
  border: 1px solid rgb(232 198 117 / 55%);
  border-radius: 0.6rem;
  color: #f8edcf;
  background: rgb(19 28 24 / 82%);
  font-size: 0.85rem;
  backdrop-filter: blur(2px);
}

.map-tick-button:hover:not(:disabled) {
  color: #18251f;
  background: #e8c675;
}

.map-tick-button:disabled {
  cursor: wait;
  opacity: 0.7;
}

.town-map-hud {
  min-width: 0;
}

/* The map column now outgrows the profile; sticking it keeps an NPC's state
   in view while the player talks to them further down the page. */
.town-map-hud :deep(.npc-detail-panel) {
  position: sticky;
  top: 1rem;
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
  .town-header-content {
    align-items: stretch;
    flex-direction: column;
  }

  .demo-reset-button {
    align-self: flex-start;
  }

  .town-play-layout {
    grid-template-columns: 1fr;
  }

  /* Single column would read map -> chat -> profile; put the profile back
     next to the map so the chat still follows the NPC's state. */
  .town-game-host-column {
    display: contents;
  }

  .town-game-stage {
    order: 1;
  }

  .town-map-hud {
    order: 2;
    margin-top: 1rem;
  }

  .town-game-host-column :deep(.npc-chat-panel) {
    order: 3;
    margin-top: 1rem;
  }

  .town-map-hud :deep(.npc-detail-panel) {
    position: static;
  }
}
</style>
