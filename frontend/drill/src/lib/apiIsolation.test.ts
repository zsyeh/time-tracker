// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { api } from './api'
import { cachedQuestion, configureWorkspaceScope, fetchQuestion } from './workspace'
import { setLearningUser } from '../../../shared/foregroundTimer'

afterEach(() => { vi.unstubAllGlobals(); setLearningUser('') })
const reply = (body: unknown) => ({ ok: true, status: 200, json: async () => body }) as Response

it('coalesces actual GETs for the same account without an extra request', async () => {
  setLearningUser('same-user')
  let resolve!: (value: Response) => void
  const fetcher = vi.fn(() => new Promise<Response>(done => { resolve = done }))
  vi.stubGlobal('fetch', fetcher)
  const a = api('/api/drill/catalog/'); const b = api('/api/drill/catalog/')
  expect(fetcher).toHaveBeenCalledOnce()
  resolve(reply({ courses: [] }))
  expect(await a).toEqual(await b)
})

it('does not reuse an older account network request or cache its private response under the new scope', async () => {
  const finishes: Array<(response: Response) => void> = []
  const fetcher = vi.fn((_url: string, _options: RequestInit) => new Promise<Response>(resolve => { finishes.push(resolve) }))
  vi.stubGlobal('fetch', fetcher)
  setLearningUser('old-user'); configureWorkspaceScope('drill:old-user', 'old-user')
  const old = fetchQuestion('same-question', '', true)
  setLearningUser('new-user'); configureWorkspaceScope('drill:new-user', 'new-user')
  const current = fetchQuestion('same-question', '', true)
  expect(fetcher).toHaveBeenCalledTimes(2)
  expect((fetcher.mock.calls[0]![1].headers as Headers).get('X-Learning-User-ID')).toBe('old-user')
  expect((fetcher.mock.calls[1]![1].headers as Headers).get('X-Learning-User-ID')).toBe('new-user')
  finishes[0]!(reply({ uuid: 'same-question', note: 'old private note' })); await old
  expect(cachedQuestion('same-question')).toBeNull()
  finishes[1]!(reply({ uuid: 'same-question', note: 'new private note' })); await current
  expect(cachedQuestion('same-question')?.note).toBe('new private note')
})
