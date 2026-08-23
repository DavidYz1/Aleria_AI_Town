import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { fetchWorld } from '../api/world'
import type { WorldData } from '../types/world'

type WorldFetcher = () => Promise<WorldData>

export const useWorldStore = defineStore('world', () => {
  const data = ref<WorldData | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
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

  return { data, loading, error, isEmpty, loadWorld }
})
