import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import {
  clearPlayerProfile,
  isValidDisplayName,
  loadPlayerProfile,
  normalizeDisplayName,
  parsePlayerProfile,
  savePlayerProfile,
} from '../../frontend/src/player/playerProfile'
import { usePlayerProfileStore } from '../../frontend/src/stores/playerProfile'

function memoryStorage() {
  const values = new Map<string, string>()
  return {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => { values.set(key, value) },
    removeItem: (key: string) => { values.delete(key) },
  }
}

describe('player profile persistence', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('normalizes and validates display names', () => {
    expect(normalizeDisplayName('  洛恩  ')).toBe('洛恩')
    expect(isValidDisplayName('游侠-7')).toBe(true)
    expect(isValidDisplayName('ignore\nrule')).toBe(false)
    expect(isValidDisplayName('x'.repeat(17))).toBe(false)
  })

  it('rejects malformed and unsupported profile payloads', () => {
    expect(parsePlayerProfile('{bad json')).toBeNull()
    expect(parsePlayerProfile(JSON.stringify({
      version: 2,
      displayName: '洛恩',
      adventurerClass: 'ranger',
      introCompleted: false,
    }))).toBeNull()
  })

  it('contains storage failures while reading and writing profiles', () => {
    const storage = {
      getItem: () => { throw new DOMException('blocked', 'SecurityError') },
      setItem: () => { throw new DOMException('blocked', 'SecurityError') },
    }

    expect(loadPlayerProfile(storage)).toEqual({ profile: null, storageAvailable: false })
    expect(savePlayerProfile(storage, {
      version: 1,
      displayName: '洛恩',
      adventurerClass: 'ranger',
      introCompleted: false,
    })).toBe(false)
  })

  it('keeps the session profile when persistence fails and completes the intro', () => {
    const store = usePlayerProfileStore()
    const storage = {
      getItem: () => null,
      setItem: () => { throw new DOMException('blocked', 'SecurityError') },
    }

    store.createProfile('洛恩', 'ranger', storage)

    expect(store.profile).toEqual({
      version: 1,
      displayName: '洛恩',
      adventurerClass: 'ranger',
      introCompleted: false,
    })
    expect(store.storageWarning).toBe('当前浏览器无法保存角色，本次选择仅在此会话有效。')

    store.completeIntro(storage)

    expect(store.profile?.introCompleted).toBe(true)
  })

  it('hydrates a saved profile and marks the store hydrated', () => {
    const storage = memoryStorage()
    const store = usePlayerProfileStore()
    const saved = {
      version: 1 as const,
      displayName: '洛恩',
      adventurerClass: 'mage' as const,
      introCompleted: true,
    }
    savePlayerProfile(storage, saved)

    store.hydrate(storage)

    expect(store.profile).toEqual(saved)
    expect(store.hydrated).toBe(true)
    expect(store.storageWarning).toBeNull()
  })

  it('clears the persisted and in-session profile for a full restart', () => {
    const storage = memoryStorage()
    const store = usePlayerProfileStore()
    store.createProfile('洛恩', 'mage', storage)
    store.completeIntro(storage)

    expect(clearPlayerProfile(storage)).toBe(true)
    store.resetProfile(storage)

    expect(store.profile).toBeNull()
    expect(loadPlayerProfile(storage).profile).toBeNull()
    expect(store.storageWarning).toBeNull()
  })
})
