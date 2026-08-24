export type AdventurerClass = 'mage' | 'ranger' | 'cleric'

export interface LocalPlayerProfileV1 {
  version: 1
  displayName: string
  adventurerClass: AdventurerClass
  introCompleted: boolean
}

export interface AdventurerClassMeta {
  id: AdventurerClass
  title: '法师' | '游侠' | '牧师'
  description: string
}

export type ProfileStorage = Pick<Storage, 'getItem' | 'setItem'>

export const PLAYER_PROFILE_STORAGE_KEY = 'aleria.player-profile.v1'

export const ADVENTURER_CLASSES: readonly AdventurerClassMeta[] = [
  { id: 'mage', title: '法师', description: '循着微光与古老符文寻找失落的答案。' },
  { id: 'ranger', title: '游侠', description: '相信脚印、风向与亲眼确认的事实。' },
  { id: 'cleric', title: '牧师', description: '用耐心和信念守护仍值得挽回的人。' },
]

const DISPLAY_NAME_PATTERN = /^[\p{Script=Han}A-Za-z0-9 ·-]{1,16}$/u

export function normalizeDisplayName(displayName: string): string {
  return displayName.trim()
}

export function isValidDisplayName(displayName: string): boolean {
  return DISPLAY_NAME_PATTERN.test(normalizeDisplayName(displayName))
}

function isAdventurerClass(value: unknown): value is AdventurerClass {
  return value === 'mage' || value === 'ranger' || value === 'cleric'
}

export function parsePlayerProfile(raw: string): LocalPlayerProfileV1 | null {
  let value: unknown
  try {
    value = JSON.parse(raw)
  } catch {
    return null
  }

  if (typeof value !== 'object' || value === null || Array.isArray(value)) return null
  const candidate = value as Record<string, unknown>
  if (candidate.version !== 1) return null
  if (typeof candidate.displayName !== 'string') return null
  if (typeof candidate.introCompleted !== 'boolean') return null
  if (!isAdventurerClass(candidate.adventurerClass)) return null

  const displayName = normalizeDisplayName(candidate.displayName)
  if (!isValidDisplayName(displayName)) return null

  return {
    version: 1,
    displayName,
    adventurerClass: candidate.adventurerClass,
    introCompleted: candidate.introCompleted,
  }
}

export function loadPlayerProfile(
  storage: ProfileStorage | null,
): { profile: LocalPlayerProfileV1 | null; storageAvailable: boolean } {
  if (storage === null) return { profile: null, storageAvailable: false }

  try {
    const raw = storage.getItem(PLAYER_PROFILE_STORAGE_KEY)
    return {
      profile: raw === null ? null : parsePlayerProfile(raw),
      storageAvailable: true,
    }
  } catch {
    return { profile: null, storageAvailable: false }
  }
}

export function savePlayerProfile(
  storage: ProfileStorage | null,
  profile: LocalPlayerProfileV1,
): boolean {
  if (storage === null) return false

  const displayName = normalizeDisplayName(profile.displayName)
  if (profile.version !== 1
    || !isValidDisplayName(displayName)
    || !isAdventurerClass(profile.adventurerClass)
    || typeof profile.introCompleted !== 'boolean') return false

  const normalizedProfile: LocalPlayerProfileV1 = {
    version: 1,
    displayName,
    adventurerClass: profile.adventurerClass,
    introCompleted: profile.introCompleted,
  }

  try {
    storage.setItem(PLAYER_PROFILE_STORAGE_KEY, JSON.stringify(normalizedProfile))
    return true
  } catch {
    return false
  }
}

export function getBrowserProfileStorage(): ProfileStorage | null {
  try {
    return typeof window === 'undefined' ? null : window.localStorage
  } catch {
    return null
  }
}
