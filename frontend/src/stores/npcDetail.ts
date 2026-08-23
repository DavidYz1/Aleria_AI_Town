import { defineStore } from 'pinia'
import { ref } from 'vue'

import { fetchNpcDetail, NpcNotFoundError } from '../api/npc'
import type { NpcDetailData } from '../types/npc'


type NpcDetailFetcher = (npcId: string) => Promise<NpcDetailData>

export const useNpcDetailStore = defineStore('npcDetail', () => {
  const selectedNpcId = ref<string | null>(null)
  const data = ref<NpcDetailData | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  let requestVersion = 0

  async function requestDetail(
    npcId: string,
    fetcher: NpcDetailFetcher,
    clearCurrentData: boolean,
  ): Promise<void> {
    const version = ++requestVersion
    loading.value = true
    error.value = null
    if (clearCurrentData) data.value = null

    try {
      const detail = await fetcher(npcId)
      if (version !== requestVersion || selectedNpcId.value !== npcId) return
      data.value = detail
    } catch (caught) {
      if (version !== requestVersion || selectedNpcId.value !== npcId) return
      error.value = caught instanceof NpcNotFoundError
        ? '没有找到这位居民。'
        : '居民详情加载失败，请稍后重试。'
    } finally {
      if (version === requestVersion && selectedNpcId.value === npcId) {
        loading.value = false
      }
    }
  }

  async function selectNpc(
    npcId: string,
    fetcher: NpcDetailFetcher = fetchNpcDetail,
  ): Promise<void> {
    selectedNpcId.value = npcId
    await requestDetail(npcId, fetcher, true)
  }

  async function refresh(
    fetcher: NpcDetailFetcher = fetchNpcDetail,
  ): Promise<void> {
    const npcId = selectedNpcId.value
    if (npcId === null) return
    await requestDetail(npcId, fetcher, false)
  }

  async function retry(
    fetcher: NpcDetailFetcher = fetchNpcDetail,
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
