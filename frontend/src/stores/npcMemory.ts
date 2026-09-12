import { defineStore } from 'pinia'
import { ref } from 'vue'

import { fetchNpcMemoryExplanations, NpcNotFoundError } from '../api/npc'
import type { NpcMemoryExplanationsData } from '../types/npc'


type NpcMemoryFetcher = (npcId: string) => Promise<NpcMemoryExplanationsData>

// Memory explanations own their loading, error and request identity so a failed
// cognition read never degrades the authoritative NPC detail panel.
export const useNpcMemoryStore = defineStore('npcMemory', () => {
  const selectedNpcId = ref<string | null>(null)
  const data = ref<NpcMemoryExplanationsData | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  let requestVersion = 0

  async function requestMemory(
    npcId: string,
    fetcher: NpcMemoryFetcher,
    clearCurrentData: boolean,
  ): Promise<void> {
    const version = ++requestVersion
    loading.value = true
    error.value = null
    if (clearCurrentData) data.value = null

    try {
      const explanations = await fetcher(npcId)
      if (version !== requestVersion || selectedNpcId.value !== npcId) return
      data.value = explanations
    } catch (caught) {
      if (version !== requestVersion || selectedNpcId.value !== npcId) return
      error.value = caught instanceof NpcNotFoundError
        ? '没有找到这位居民。'
        : '相关记忆暂时无法读取，请稍后重试。'
    } finally {
      if (version === requestVersion && selectedNpcId.value === npcId) {
        loading.value = false
      }
    }
  }

  async function selectNpc(
    npcId: string,
    fetcher: NpcMemoryFetcher = fetchNpcMemoryExplanations,
  ): Promise<void> {
    selectedNpcId.value = npcId
    await requestMemory(npcId, fetcher, true)
  }

  async function refresh(
    fetcher: NpcMemoryFetcher = fetchNpcMemoryExplanations,
  ): Promise<void> {
    const npcId = selectedNpcId.value
    if (npcId === null) return
    await requestMemory(npcId, fetcher, false)
  }

  async function retry(
    fetcher: NpcMemoryFetcher = fetchNpcMemoryExplanations,
  ): Promise<void> {
    await refresh(fetcher)
  }

  function close(): void {
    requestVersion += 1
    selectedNpcId.value = null
    data.value = null
    loading.value = false
    error.value = null
  }

  return {
    selectedNpcId,
    data,
    loading,
    error,
    selectNpc,
    refresh,
    retry,
    close,
  }
})
