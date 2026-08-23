import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import {
  advanceWorldTick,
  fetchWorld,
  WorldTickConflictError,
} from '../api/world'
import type { WorldData } from '../types/world'
import type { WorldTickData } from '../types/worldTick'

type WorldFetcher = () => Promise<WorldData>
type TickAdvancer = (expectedTick: number) => Promise<WorldTickData>

export const useWorldStore = defineStore('world', () => {
  const data = ref<WorldData | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const advancing = ref(false)
  const tickError = ref<string | null>(null)
  const lastTick = ref<WorldTickData | null>(null)
  const isEmpty = computed(
    () => data.value !== null && (data.value.locations.length === 0 || data.value.npcs.length === 0),
  )

  async function loadWorld(fetcher: WorldFetcher = fetchWorld): Promise<void> {
    loading.value = true
    error.value = null

    try {
      data.value = await fetcher()
    } catch {
      data.value = null
      error.value = '世界加载失败，请稍后重试。'
    } finally {
      loading.value = false
    }
  }

  async function advanceTick(
    advancer: TickAdvancer = advanceWorldTick,
    reloader: WorldFetcher = fetchWorld,
  ): Promise<void> {
    if (advancing.value || data.value === null) return

    advancing.value = true
    tickError.value = null
    try {
      const result = await advancer(data.value.world.tick)
      data.value = result.world
      lastTick.value = result
    } catch (caught) {
      if (caught instanceof WorldTickConflictError) {
        lastTick.value = null
        await loadWorld(reloader)
        tickError.value = '世界已在其他请求中推进，已为你刷新最新状态。'
      } else {
        tickError.value = '时间推进失败，当前世界状态未改变。'
      }
    } finally {
      advancing.value = false
    }
  }

  return {
    data,
    loading,
    error,
    advancing,
    tickError,
    lastTick,
    isEmpty,
    loadWorld,
    advanceTick,
  }
})
