// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { api } from './api'
import { cachedCatalog, cachedHeatmap, cachedNoteDraft, cachedQuestion, cachedQuestionPage, clearNoteDraft, configureWorkspaceScope, fetchCatalog, fetchQuestion, storeHeatmap, storeNoteDraft, storeQuestion, storeQuestionPage } from './workspace'
import type { Catalog, Page, QuestionDetail, QuestionSummary } from '../types'
vi.mock('./api', () => ({ api: vi.fn() }))
afterEach(() => vi.restoreAllMocks())
beforeEach(() => { vi.clearAllMocks(); configureWorkspaceScope('reset'); sessionStorage.clear(); localStorage.clear() })
it('isolates account/workspace memory and persisted caches while retaining each scope on return', async () => {
  configureWorkspaceScope('drill:user-a')
  const detail = { uuid: 'same-id', note: 'private a' } as QuestionDetail
  const page = { results: [detail] } as unknown as Page<QuestionSummary>
  const catalog = { name: 'a' } as unknown as Catalog
  storeQuestion(detail.uuid, '', detail); storeQuestionPage('list', page); storeHeatmap('all', { count: 8 }); storeNoteDraft(detail.uuid, 'private draft')
  vi.mocked(api).mockResolvedValueOnce(catalog); await fetchCatalog()
  for (const scope of ['ei:user-a', 'drill:user-b']) {
    configureWorkspaceScope(scope)
    expect(cachedQuestion(detail.uuid)).toBeNull(); expect(cachedQuestionPage('list')).toBeNull()
    expect(cachedHeatmap('all')).toBeNull(); expect(cachedCatalog()).toBeNull(); expect(cachedNoteDraft(detail.uuid)).toBeNull()
  }
  expect(sessionStorage.getItem('drill.question-list.v2.drill%3Auser-a.list')).not.toBeNull()
  expect(sessionStorage.getItem('drill.question-list.v2.ei%3Auser-a.list')).toBeNull()
  configureWorkspaceScope('drill:user-a')
  expect(cachedQuestion(detail.uuid)?.note).toBe('private a')
  expect(cachedQuestionPage('list')).toEqual(page); expect(cachedHeatmap('all')).toEqual({ count: 8 })
  expect(cachedCatalog()).toEqual(catalog); expect(cachedNoteDraft(detail.uuid)).toBe('private draft')
})
it('does not reuse an unscoped legacy catalog', () => {
  localStorage.setItem('drill.taxonomy.v1', JSON.stringify({ savedAt: Date.now(), value: { name: 'legacy unknown workspace' } }))
  configureWorkspaceScope('fresh:ei'); expect(cachedCatalog()).toBeNull()
})
it('does not cache late responses under another scope or delete its newer in-flight request', async () => {
  let finishOld!: (value: QuestionDetail) => void
  let finishNew!: (value: QuestionDetail) => void
  let finishCatalog!: (value: Catalog) => void
  configureWorkspaceScope('old:drill')
  vi.mocked(api).mockImplementationOnce(() => new Promise(resolve => { finishOld = resolve as typeof finishOld }))
    .mockImplementationOnce(() => new Promise(resolve => { finishCatalog = resolve as typeof finishCatalog }))
    .mockImplementationOnce(() => new Promise(resolve => { finishNew = resolve as typeof finishNew }))
  const old = fetchQuestion('shared-id'); const catalog = fetchCatalog(true)
  configureWorkspaceScope('new:ei')
  const newer = fetchQuestion('shared-id')
  finishOld({ uuid: 'shared-id', note: 'old account' } as QuestionDetail)
  finishCatalog({ name: 'old catalog' } as unknown as Catalog)
  await old; await catalog
  expect(cachedQuestion('shared-id')).toBeNull(); expect(cachedCatalog()).toBeNull()
  expect(fetchQuestion('shared-id')).toBe(newer)
  finishNew({ uuid: 'shared-id', note: 'new account' } as QuestionDetail); await newer
  expect(cachedQuestion('shared-id')?.note).toBe('new account')
  expect(api).toHaveBeenCalledTimes(3)
})

it('preserves the original username+UUID Note draft across the workspace cache upgrade', () => {
  const legacyKey = 'drill.note-draft.v1.existing-user.old-question'
  localStorage.setItem(legacyKey, JSON.stringify({ value: 'unsynced before upgrade', savedAt: Date.now() }))
  configureWorkspaceScope('drill:existing-user', 'existing-user')
  expect(cachedNoteDraft('old-question')).toBe('unsynced before upgrade')
  expect(storeNoteDraft('old-question', 'edited after upgrade')).toBe(true)
  expect(JSON.parse(localStorage.getItem(legacyKey)!).value).toBe('edited after upgrade')
  configureWorkspaceScope('ei:existing-user', 'existing-user')
  expect(cachedNoteDraft('different-question')).toBeNull()
  configureWorkspaceScope('drill:other-user', 'other-user')
  expect(cachedNoteDraft('old-question')).toBeNull()
  configureWorkspaceScope('drill:existing-user', 'existing-user')
  clearNoteDraft('old-question')
  expect(localStorage.getItem(legacyKey)).toBeNull()
  configureWorkspaceScope('ei:existing-user', 'existing-user')
  configureWorkspaceScope('drill:existing-user', 'existing-user')
  expect(cachedNoteDraft('old-question')).toBeNull()
})
it('keeps the old persisted draft and the latest in-memory edit when Note storage fails', () => {
  const legacyKey = 'drill.note-draft.v1.quota-user.legacy-question'
  localStorage.setItem(legacyKey, JSON.stringify({ value: 'old persisted note', savedAt: Date.now() }))
  configureWorkspaceScope('drill:quota-user', 'quota-user')
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('quota') })
  expect(storeNoteDraft('legacy-question', 'latest unpersisted note')).toBe(false)
  expect(cachedNoteDraft('legacy-question')).toBe('latest unpersisted note')
  expect(JSON.parse(localStorage.getItem(legacyKey)!).value).toBe('old persisted note')
  vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => { throw new Error('denied') })
  clearNoteDraft('legacy-question')
  expect(cachedNoteDraft('legacy-question')).toBeNull()
})
