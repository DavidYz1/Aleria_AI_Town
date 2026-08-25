import { defineStore } from 'pinia'
import { ref } from 'vue'

import {
  ADVENTURER_CLASSES,
  clearPlayerProfile,
  getBrowserProfileStorage,
  isValidDisplayName,
  loadPlayerProfile,
  normalizeDisplayName,
  savePlayerProfile,
} from '../player/playerProfile'
import type {
  AdventurerClass,
  LocalPlayerProfileV1,
  ProfileStorage,
} from '../player/playerProfile'

const STORAGE_WARNING = '当前浏览器无法保存角色，本次选择仅在此会话有效。'

export const usePlayerProfileStore = defineStore('playerProfile', () => {
  const profile = ref<LocalPlayerProfileV1 | null>(null)
  const hydrated = ref(false)
  const storageWarning = ref<string | null>(null)

  function hydrate(storage: ProfileStorage | null = getBrowserProfileStorage()): void {
    const result = loadPlayerProfile(storage)
    profile.value = result.profile
    hydrated.value = true
    storageWarning.value = result.storageAvailable ? null : STORAGE_WARNING
  }

  function createProfile(
    displayName: string,
    adventurerClass: AdventurerClass,
    storage: ProfileStorage | null = getBrowserProfileStorage(),
  ): void {
    const normalizedName = normalizeDisplayName(displayName)
    if (!isValidDisplayName(normalizedName)
      || !ADVENTURER_CLASSES.some(({ id }) => id === adventurerClass)) return

    const nextProfile: LocalPlayerProfileV1 = {
      version: 1,
      displayName: normalizedName,
      adventurerClass,
      introCompleted: false,
    }
    const saved = savePlayerProfile(storage, nextProfile)
    profile.value = nextProfile
    storageWarning.value = saved ? null : STORAGE_WARNING
  }

  function completeIntro(
    storage: ProfileStorage | null = getBrowserProfileStorage(),
  ): void {
    if (profile.value === null) return

    const nextProfile: LocalPlayerProfileV1 = {
      ...profile.value,
      introCompleted: true,
    }
    const saved = savePlayerProfile(storage, nextProfile)
    profile.value = nextProfile
    storageWarning.value = saved ? null : STORAGE_WARNING
  }

  function resetProfile(
    storage: ProfileStorage | null = getBrowserProfileStorage(),
  ): void {
    const cleared = clearPlayerProfile(storage)
    profile.value = null
    storageWarning.value = cleared ? null : STORAGE_WARNING
  }

  return {
    profile,
    hydrated,
    storageWarning,
    hydrate,
    createProfile,
    completeIntro,
    resetProfile,
  }
})
