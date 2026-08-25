import { describe, expect, it } from 'vitest'

import { resolveApiBaseUrl } from '../../frontend/src/api/client'


describe('API base URL selection', () => {
  it('uses the same origin for an unconfigured production build', () => {
    expect(resolveApiBaseUrl(undefined, true)).toBe('/')
  })

  it('keeps the local backend default during development', () => {
    expect(resolveApiBaseUrl(undefined, false)).toBe('http://127.0.0.1:8000')
  })

  it('honors an explicit deployment URL', () => {
    expect(resolveApiBaseUrl(' https://api.example.test ', true)).toBe(
      'https://api.example.test',
    )
  })
})
