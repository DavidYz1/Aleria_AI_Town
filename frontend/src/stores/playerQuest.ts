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
  ): Promise<void> {
    const version = ++stateRequestVersion
    loading.value = true
    error.value = null

    try {
      const result = await fetcher()
      if (version !== stateRequestVersion) return
      data.value = result
    } catch {
      if (version !== stateRequestVersion) return
      error.value = '玩家任务加载失败，请稍后重试。'
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
    traveller: PlayerTraveller = travelPlayer,
  ): Promise<void> {
    await mutate(() => traveller(locationId))
  }

  async function interact(
    interaction: QuestInteraction,
    interactor: QuestInteractor = interactWithMissingChildQuest,
  ): Promise<void> {
    const current = data.value
    if (current === null) return
    await mutate(() => interactor({
      interaction,
      expected_version: current.quest.version,
    }))
  }

  async function mutate(
    operation: () => Promise<PlayerQuestData>,
  ): Promise<void> {
    if (mutating.value || data.value === null) return

    const stateVersion = ++stateRequestVersion
    const mutationVersion = ++mutationRequestVersion
    mutating.value = true
    mutationError.value = null

    try {
      const result = await operation()
      if (stateVersion !== stateRequestVersion) return
      data.value = result
    } catch (caught) {
      if (stateVersion !== stateRequestVersion) return
      if (caught instanceof PlayerQuestConflictError) {
        await load()
        mutationError.value = error.value === null
          ? '任务状态已更新，已刷新最新进度。'
          : '任务状态已更新，但刷新失败，请重试。'
      } else {
        mutationError.value = '操作失败，当前玩家与任务状态未改变。'
      }
    } finally {
      if (mutationVersion === mutationRequestVersion) {
        mutating.value = false
      }
    }
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
  }
})
