<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

import type {
  NpcVisualProjection,
  TownGameController,
  TownGameFactory,
} from '../game/contracts'
import type { LocalPlayerProfileV1 } from '../player/playerProfile'

const props = defineProps<{
  profile: LocalPlayerProfileV1
  npcs: NpcVisualProjection[]
  factory?: TownGameFactory
}>()

const emit = defineEmits<{
  npcSelected: [npcId: string]
}>()

const mountElement = ref<HTMLElement | null>(null)
const loading = ref(true)
const loadError = ref<string | null>(null)
let controller: TownGameController | null = null
let generation = 0

async function startGame(): Promise<void> {
  const parent = mountElement.value
  if (parent === null) return

  const currentGeneration = ++generation
  loading.value = true
  loadError.value = null
  try {
    const factory = props.factory ?? await defaultFactory()
    const nextController = await factory(
      parent,
      {
        profile: { ...props.profile },
        npcs: props.npcs.map((npc) => ({ ...npc })),
      },
      {
        onNpcSelected(npcId) {
          if (currentGeneration === generation) emit('npcSelected', npcId)
        },
        onLoadFailed(message) {
          if (currentGeneration !== generation) return
          loadError.value = message
          loading.value = false
        },
      },
    )
    if (currentGeneration !== generation) {
      nextController.destroy()
      return
    }
    controller = nextController
    loading.value = false
  } catch {
    if (currentGeneration !== generation) return
    loadError.value = '地图资源加载失败，请重试。'
    loading.value = false
  }
}

async function retry(): Promise<void> {
  generation += 1
  controller?.destroy()
  controller = null
  await startGame()
}

async function defaultFactory(): Promise<TownGameFactory> {
  const { createTownGame } = await import('../game/createTownGame')
  return createTownGame
}

watch(
  () => props.npcs,
  (npcs) => controller?.updateNpcs(npcs.map((npc) => ({ ...npc }))),
  { deep: true },
)

onMounted(() => {
  void startGame()
})

onBeforeUnmount(() => {
  generation += 1
  controller?.destroy()
  controller = null
})
</script>

<template>
  <section class="town-game-frame" aria-label="曦谷地图">
    <div ref="mountElement" class="town-game-mount" />
    <p v-if="loading" class="town-game-status" role="status" aria-live="polite">
      正在绘制曦谷地图…
    </p>
    <div v-if="loadError" class="town-game-error" role="alert">
      <p>{{ loadError }}</p>
      <button type="button" @click="retry">重试加载地图</button>
    </div>
  </section>
</template>

<style scoped>
.town-game-frame {
  position: relative;
  min-height: 28rem;
  overflow: hidden;
  border: 1px solid rgb(184 154 96 / 45%);
  border-radius: 1rem;
  background: #18251f;
  box-shadow: inset 0 0 3rem rgb(0 0 0 / 28%);
}

.town-game-mount {
  position: absolute;
  inset: 0;
}

.town-game-mount :deep(canvas) {
  display: block;
  image-rendering: pixelated;
  outline: none;
}

.town-game-mount :deep(canvas:focus-visible) {
  outline: 3px solid #e8c675;
  outline-offset: -3px;
}

.town-game-status,
.town-game-error {
  position: absolute;
  z-index: 2;
  inset: 50% auto auto 50%;
  transform: translate(-50%, -50%);
  margin: 0;
  padding: 0.9rem 1.1rem;
  border-radius: 0.65rem;
  color: #f8edcf;
  background: rgb(19 28 24 / 88%);
  text-align: center;
}

.town-game-error button {
  margin-top: 0.6rem;
}

@media (max-width: 760px) {
  .town-game-frame {
    min-height: 22rem;
  }
}
</style>
