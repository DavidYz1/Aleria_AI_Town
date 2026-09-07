import { defineStore } from 'pinia'
import { ref } from 'vue'

import {
  fetchPlayerQuest,
  interactWithMissingChildQuest,
  PlayerQuestConflictError,
  travelPlayer,
} from '../api/playerQuest'
import type {
  PlayerQuestData,
  PlayerQuestFetcher,
  PlayerTraveller,
  QuestInteraction,
  QuestInteractor,
} from '../types/playerQuest'

type WorldRefresher = () => Promise<boolean>

export const usePlayerQuestStore = defineStore('playerQuest', () => {
  const data = ref<PlayerQuestData | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const mutating = ref(false)
  const mutationError = ref<string | null>(null)
  let stateRequestVersion = 0
  let mutationRequestVersion = 0

  async function load(
    fetcher: PlayerQuestFetcher = fetchPlayerQuest,
  ): Promise<boolean> {
    const version = ++stateRequestVersion
    loading.value = true
    error.value = null

    try {
      const result = await fetcher()
      if (version !== stateRequestVersion) return false
      data.value = result
      return true
    } catch {
      if (version !== stateRequestVersion) return false
      error.value = '玩家任务加载失败，请稍后重试。'
      return false
    } finally {
      if (version === stateRequestVersion) loading.value = false
    }
  }

  async function retry(
    fetcher: PlayerQuestFetcher = fetchPlayerQuest,
  ): Promise<void> {
    await load(fetcher)
  }

  async function travel(
    locationId: string,
    expectedWorldVersion: number,
    traveller: PlayerTraveller = travelPlayer,
    refreshWorld: WorldRefresher = async () => true,
  ): Promise<boolean> {
    return mutate(() => traveller(locationId, expectedWorldVersion), refreshWorld)
  }

  async function interact(
    interaction: QuestInteraction,
    expectedWorldVersion: number,
    interactor: QuestInteractor = interactWithMissingChildQuest,
    refreshWorld: WorldRefresher = async () => true,
  ): Promise<void> {
    const current = data.value
    if (current === null) return
    await mutate(() => interactor({
      interaction,
      expected_version: current.quest.version,
      expected_world_version: expectedWorldVersion,
    }), refreshWorld)
  }

  async function mutate(
    operation: () => Promise<PlayerQuestData>,
    refreshWorld: WorldRefresher,
  ): Promise<boolean> {
    if (mutating.value || data.value === null) return false

    const stateVersion = ++stateRequestVersion
    const mutationVersion = ++mutationRequestVersion
    mutating.value = true
    mutationError.value = null

    try {
      const result = await operation()
      if (stateVersion !== stateRequestVersion) return false
      data.value = result
      const worldRefreshed = await safelyRefreshWorld(refreshWorld)
      if (stateVersion !== stateRequestVersion) return false
      if (!worldRefreshed) {
        mutationError.value = '操作已完成，但世界刷新失败，请重试。'
        return false
      }
      return true
    } catch (caught) {
      if (stateVersion !== stateRequestVersion) return false
      if (caught instanceof PlayerQuestConflictError) {
        const [playerRefreshed, worldRefreshed] = await Promise.all([
          load(),
          safelyRefreshWorld(refreshWorld),
        ])
        if (mutationVersion !== mutationRequestVersion) return false
        mutationError.value = playerRefreshed && worldRefreshed
          ? '任务状态已更新，已刷新最新进度。'
          : '任务状态已更新，但刷新失败，请重试。'
      } else {
        mutationError.value = '操作失败，当前玩家与任务状态未改变。'
      }
      return false
    } finally {
      if (mutationVersion === mutationRequestVersion) {
        mutating.value = false
      }
    }
  }

  async function safelyRefreshWorld(refreshWorld: WorldRefresher): Promise<boolean> {
    try {
      return await refreshWorld()
    } catch {
      return false
    }
  }

  function reset(): void {
    stateRequestVersion += 1
    mutationRequestVersion += 1
    data.value = null
    loading.value = false
    error.value = null
    mutating.value = false
    mutationError.value = null
  }

  return {
    data,
    loading,
    error,
    mutating,
    mutationError,
    load,
    retry,
    travel,
    interact,
    reset,
  }
})
