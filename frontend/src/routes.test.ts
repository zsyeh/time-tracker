import { describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { routes } from './routes'

function testRouter() {
  return createRouter({ history: createMemoryHistory(), routes })
}

describe('application route resources', () => {
  it.each([
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

  it('redirects the legacy root to Today', () => {
    expect(routes.find((route) => route.path === '/')?.redirect).toBe('/today')
  })

  it('marks only the public share route as anonymous', () => {
    const router = testRouter()
    expect(router.resolve('/share/token').meta.public).toBe(true)
    expect(router.resolve('/sessions/123e4567-e89b-12d3-a456-426614174000').meta.public).not.toBe(true)
  })
})
