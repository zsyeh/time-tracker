import { describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { routes } from './routes'

function testRouter() {
  return createRouter({ history: createMemoryHistory(), routes })
}

describe('application route resources', () => {
  it.each([
    ['/', 'today'],
    ['/today', 'today'],
    ['/trends', 'trends'],
    ['/sessions', 'sessions'],
    ['/sessions/123e4567-e89b-12d3-a456-426614174000', 'session-detail'],
    ['/issues', 'issues'],
    ['/settings', 'settings'],
    ['/share/share_token', 'public-share'],
  ])('maps %s to %s', (path, name) => {
    const router = testRouter()
    expect(router.resolve(path).name).toBe(name)
  })

  it('serves Today at root without redirecting and retains the /today alias', () => {
    const root = routes.find((route) => route.path === '/')
    expect(root?.redirect).toBeUndefined()
    expect(root?.alias).toBe('/today')
    expect(testRouter().resolve('/?active=123').fullPath).toBe('/?active=123')
  })

  it('marks only the public share route as anonymous', () => {
    const router = testRouter()
    expect(router.resolve('/share/token').meta.public).toBe(true)
    expect(router.resolve('/sessions/123e4567-e89b-12d3-a456-426614174000').meta.public).not.toBe(true)
  })
})
