// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { api } from './api'
import { cachedHeatmap, cachedNoteDraft, cachedQuestion, cachedQuestionPage, clearNoteDraft, configureWorkspaceScope, fetchCatalog, fetchQuestion, patchQuestionState, storeHeatmap, storeNoteDraft, storeQuestionPage } from './workspace'
import type { Catalog, Page, QuestionDetail, QuestionSummary } from '../types'
vi.mock('./api', () => ({ api: vi.fn() }))
beforeEach(() => { vi.clearAllMocks(); configureWorkspaceScope('reliability-test'); sessionStorage.clear(); localStorage.clear() })
afterEach(() => vi.restoreAllMocks())
function denyWrites() { vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new DOMException('full', 'QuotaExceededError') }) }
it('returns successful detail and catalog responses when storage is full, retaining memory caches', async () => {
  denyWrites()
  const detail = { uuid: 'quota-detail', note: 'saved' } as QuestionDetail
  const catalog = { courses: [] } as unknown as Catalog
  vi.mocked(api).mockResolvedValueOnce(detail).mockResolvedValueOnce(catalog)
  expect(await fetchQuestion(detail.uuid)).toBe(detail)
  expect(cachedQuestion(detail.uuid)).toBe(detail)
  expect(await fetchCatalog(true)).toBe(catalog)
  const page = { results: [] } as unknown as Page<QuestionSummary>
  storeQuestionPage('quota-page', page); storeHeatmap('quota-heatmap', { count: 5 })
  expect(cachedQuestionPage('quota-page')).toBe(page)
  expect(cachedHeatmap('quota-heatmap')).toEqual({ count: 5 })
})
it('patches saved state and dispatches invalidation even when browser storage cannot be read or written', async () => {
  const detail = { uuid: 'blocked-detail', note: 'old' } as QuestionDetail
  vi.mocked(api).mockResolvedValueOnce(detail); await fetchQuestion(detail.uuid)
  const listener = vi.fn(); window.addEventListener('drill:question-state-changed', listener)
  const sessionGetter = vi.spyOn(window, 'sessionStorage', 'get').mockImplementation(() => { throw new Error('denied') })
  denyWrites()
  expect(() => patchQuestionState(detail.uuid, { note: 'server confirmed' })).not.toThrow()
  expect(cachedQuestion(detail.uuid)?.note).toBe('server confirmed')
  expect(listener).toHaveBeenCalledTimes(1)
  sessionGetter.mockRestore(); window.removeEventListener('drill:question-state-changed', listener)
})
it('reports unpersisted drafts while retaining them in scoped memory and tolerates failed removal', () => {
  denyWrites(); expect(storeNoteDraft('draft', 'unsynced note')).toBe(false)
  expect(cachedNoteDraft('draft')).toBe('unsynced note')
  configureWorkspaceScope('other-account'); expect(cachedNoteDraft('draft')).toBeNull()
  configureWorkspaceScope('reliability-test')
  vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => { throw new Error('denied') })
  expect(() => clearNoteDraft('draft')).not.toThrow()
})
it('reads a persisted note even if sessionStorage is unavailable', () => {
  expect(storeNoteDraft('persisted-note', 'saved locally')).toBe(true)
  // Simulate a fresh document without depending on the module memory fallback.
  localStorage.setItem('drill.note-draft.v1.reliability-test.fresh-note', JSON.stringify({ value: 'fresh saved note', savedAt: Date.now() }))
  vi.spyOn(window, 'sessionStorage', 'get').mockImplementation(() => { throw new Error('denied') })
  expect(cachedNoteDraft('fresh-note')).toBe('fresh saved note')
})
