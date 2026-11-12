// @vitest-environment jsdom
import { beforeEach, expect, it, vi } from 'vitest'
import { api } from './api'
import { cachedQuestion, fetchNavigationQuestion, fetchQuestion } from './workspace'
import type { QuestionDetail } from '../types'
vi.mock('./api', () => ({ api: vi.fn() }))
beforeEach(() => { vi.clearAllMocks(); sessionStorage.clear(); localStorage.clear() })
it('shares an in-flight prefetch and cancelling navigation does not abort the shared request', async () => {
  let finish!: (value: QuestionDetail) => void
  vi.mocked(api).mockImplementationOnce(() => new Promise(resolve => { finish = resolve as typeof finish }))
  const prefetch = fetchQuestion('shared-navigation')
  const controller = new AbortController()
  const navigation = fetchNavigationQuestion('shared-navigation', '', controller.signal)
  const rejected = expect(navigation).rejects.toHaveProperty('name', 'AbortError')
  controller.abort(); await rejected
  const value = { uuid: 'shared-navigation' } as QuestionDetail
  finish(value)
  expect(await prefetch).toBe(value)
  expect(api).toHaveBeenCalledTimes(1)
})
it('revalidates completed cached state and rejects already-cancelled navigation without a request', async () => {
  const first = { uuid: 'revalidate-navigation', note: 'old' } as QuestionDetail
  const latest = { uuid: 'revalidate-navigation', note: 'updated on server' } as QuestionDetail
  vi.mocked(api).mockResolvedValueOnce(first).mockResolvedValueOnce(latest)
  await fetchQuestion(first.uuid)
  expect(await fetchNavigationQuestion(first.uuid)).toBe(latest)
  expect(api).toHaveBeenCalledTimes(2)
  const controller = new AbortController(); controller.abort()
  await expect(fetchNavigationQuestion('never-request', '', controller.signal)).rejects.toHaveProperty('name', 'AbortError')
  expect(api).toHaveBeenCalledTimes(2)
})

it('shares a search-result prefetch when router query insertion order differs', async () => {
  let finish!: (value: QuestionDetail) => void
  vi.mocked(api).mockImplementationOnce(() => new Promise(resolve => { finish = resolve as typeof finish }))
  const prefetched = fetchQuestion('search-entry-order', 'status=review&q=偏导数&search_version=2')
  const navigation = fetchNavigationQuestion('search-entry-order', 'q=%E5%81%8F%E5%AF%BC%E6%95%B0&search_version=2&status=review', new AbortController().signal)
  expect(api).toHaveBeenCalledTimes(1)
  const value = { uuid: 'search-entry-order', note: 'same account' } as QuestionDetail
  finish(value)
  expect(await prefetched).toBe(value); expect(await navigation).toBe(value)
  expect(cachedQuestion(value.uuid, 'search_version=2&status=review&q=偏导数')).toBe(value)
})
