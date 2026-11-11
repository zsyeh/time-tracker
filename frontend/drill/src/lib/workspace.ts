import { api } from './api'
import { withWorkspacePrefix } from './runtimePath'
import type { Catalog, Page, QuestionDetail, QuestionSummary } from '../types'

const catalogKey = 'drill.taxonomy.v2'
const catalogTtl = 7 * 24 * 60 * 60 * 1000
const listTtl = 5 * 60 * 1000
const detailTtl = 24 * 60 * 60 * 1000
const detailLimit = 120

let cacheScope = ''
let noteCacheScope = ''
let scopeVersion = 0
let memoryCatalog: Catalog | null = null
let catalogSavedAt = 0
const listCache = new Map<string, { value: Page<QuestionSummary>; savedAt: number }>()
const detailCache = new Map<string, { value: QuestionDetail; savedAt: number }>()
const detailInflight = new Map<string, Promise<QuestionDetail>>()
const heatmapCache = new Map<string, { value: unknown; savedAt: number }>()
const stateEventKey = 'drill.question-state-event.v1'

// Browser storage is an optional cache, never part of an API transaction.
function persist(storage: 'sessionStorage' | 'localStorage', key: string, value: unknown): boolean {
  try { window[storage].setItem(key, JSON.stringify(value)); return true } catch { return false }
}
function removeStored(storage: 'sessionStorage' | 'localStorage', key: string) {
  try { window[storage].removeItem(key) } catch { /* storage may be unavailable */ }
}
function sessionKeys(): string[] {
  try { return Object.keys(sessionStorage) } catch { return [] }
}
const noteDraftMemory = new Map<string, { value: string | null; savedAt: number }>()

function invalidateDerivedCaches() {
  listCache.clear()
  heatmapCache.clear()
  if (!cacheScope) return
  for (const key of sessionKeys()) {
    if (
      key.startsWith(`drill.heatmap.v1.${cacheScope}.`) ||
      key.startsWith(`drill.question-list.v1.${cacheScope}.`)
      || key.startsWith(`drill.heatmap.v2.${cacheScope}.`)
      || key.startsWith(`drill.question-list.v2.${cacheScope}.`)
    ) removeStored('sessionStorage', key)
  }
}

if (typeof window !== 'undefined') {
  window.addEventListener('storage', (event) => {
    if (event.key !== stateEventKey || !event.newValue) return
    invalidateDerivedCaches()
    try {
      const payload = JSON.parse(event.newValue)
      if (payload?.uuid) {
        for (const key of [...detailCache.keys()]) {
          if (key.startsWith(`${payload.uuid}?`)) detailCache.delete(key)
        }
        for (const key of sessionKeys()) {
          if (key.startsWith(`drill.question-detail.v2.${cacheScope}.${encodeURIComponent(payload.uuid + '?')}`)) removeStored('sessionStorage', key)
        }
      }
      window.dispatchEvent(new CustomEvent('drill:question-state-changed', { detail: payload }))
    } catch { /* ignore malformed cross-tab events */ }
  })
}

function readStored<T>(key: string, ttl: number): T | null {
  for (const storage of ['sessionStorage', 'localStorage'] as const) {
    try {
      const stored = JSON.parse(window[storage].getItem(key) || 'null')
      if (stored && Date.now() - Number(stored.savedAt) <= ttl) return stored.value as T
    } catch { /* unavailable or corrupt cache; try the other store */ }
  }
  return null
}

function scopedKey(kind: string, key: string) {
  const schema = ['question-list', 'question-detail', 'heatmap'].includes(kind) ? 'v2' : 'v1'
  const scope = kind === 'note-draft' ? noteCacheScope : cacheScope
  return scope ? `drill.${kind}.${schema}.${scope}.${key}` : ''
}

export function configureWorkspaceScope(scope: string, noteScope = scope) {
  // Question UUIDs are globally unique. Keep the original username+UUID Note
  // namespace so existing unsynced drafts survive the cache isolation upgrade.
  noteCacheScope = encodeURIComponent(noteScope)
  const nextScope = encodeURIComponent(scope)
  if (nextScope === cacheScope) return
  cacheScope = nextScope
  scopeVersion += 1
  memoryCatalog = null
  catalogSavedAt = 0
  listCache.clear()
  detailCache.clear()
  heatmapCache.clear()
  detailInflight.clear()
}

export function cachedCatalog(): Catalog | null {
  if (memoryCatalog && Date.now() - catalogSavedAt <= catalogTtl) return memoryCatalog
  if (!cacheScope) return null
  try {
    const stored = JSON.parse(localStorage.getItem(`${catalogKey}.${cacheScope}`) || 'null')
    if (stored && Date.now() - Number(stored.savedAt) <= catalogTtl) {
      memoryCatalog = stored.value
      catalogSavedAt = Number(stored.savedAt)
      return memoryCatalog
    }
  } catch { /* ignore corrupt browser cache */ }
  return null
}

export async function fetchCatalog(force = false): Promise<Catalog> {
  if (!force) {
    const cached = cachedCatalog()
    if (cached) return cached
  }
  const requestScope = cacheScope
  const requestVersion = scopeVersion
  const value = await api<Catalog>('/api/drill/catalog/')
  if (requestScope === cacheScope && requestVersion === scopeVersion) {
    memoryCatalog = value
    catalogSavedAt = Date.now()
    if (requestScope) persist('localStorage', `${catalogKey}.${requestScope}`, { savedAt: catalogSavedAt, value })
  }
  return value
}

export function cachedQuestionPage(key: string): Page<QuestionSummary> | null {
  const memory = listCache.get(key)
  if (memory && Date.now() - memory.savedAt <= listTtl) return memory.value
  const storageKey = scopedKey('question-list', key)
  return storageKey ? readStored<Page<QuestionSummary>>(storageKey, listTtl) : null
}

export function storeQuestionPage(key: string, value: Page<QuestionSummary>) {
  const entry = { savedAt: Date.now(), value }
  listCache.set(key, entry)
  const storageKey = scopedKey('question-list', key)
  if (storageKey) persist('sessionStorage', storageKey, entry)
}

function detailKey(uuid: string, query = '') {
  return `${uuid}?${query}`
}

export function cachedQuestion(uuid: string, query = ''): QuestionDetail | null {
  const key = detailKey(uuid, query)
  const memory = detailCache.get(key)
  if (memory && Date.now() - memory.savedAt <= detailTtl) return memory.value
  const storageKey = scopedKey('question-detail', encodeURIComponent(key))
  const stored = storageKey ? readStored<QuestionDetail>(storageKey, detailTtl) : null
  if (stored) detailCache.set(key, { value: stored, savedAt: Date.now() })
  return stored
}

export function storeQuestion(uuid: string, query: string, value: QuestionDetail) {
  const key = detailKey(uuid, query)
  const entry = { savedAt: Date.now(), value }
  detailCache.set(key, entry)
  while (detailCache.size > detailLimit) detailCache.delete(detailCache.keys().next().value as string)
  const storageKey = scopedKey('question-detail', encodeURIComponent(key))
  if (storageKey) persist('sessionStorage', storageKey, entry)
}

export function fetchQuestion(uuid: string, query = '', force = false, signal?: AbortSignal): Promise<QuestionDetail> {
  const key = detailKey(uuid, query)
  if (!force) {
    const cached = cachedQuestion(uuid, query)
    if (cached) return Promise.resolve(cached)
  }
  const existing = signal ? null : detailInflight.get(key)
  if (existing) return existing
  const suffix = query ? `?${query}` : ''
  const requestScope = cacheScope
  const requestVersion = scopeVersion
  const request = api<QuestionDetail>(`/api/drill/questions/${uuid}/${suffix}`, signal ? { signal } : {})
    .then((value) => {
      if (requestScope === cacheScope && requestVersion === scopeVersion) storeQuestion(uuid, query, value)
      return value
    })
    .finally(() => { if (!signal && detailInflight.get(key) === request) detailInflight.delete(key) })
  if (!signal) detailInflight.set(key, request)
  return request
}

// Share an in-flight prefetch without cancelling it when this particular view leaves.
// Completed cached data is displayed immediately, then revalidated through this request.
export function fetchNavigationQuestion(uuid: string, query = '', signal?: AbortSignal): Promise<QuestionDetail> {
  if (signal?.aborted) return Promise.reject(new DOMException('Navigation cancelled', 'AbortError'))
  const request = fetchQuestion(uuid, query, true)
  if (!signal) return request
  return new Promise((resolve, reject) => {
    const abort = () => reject(new DOMException('Navigation cancelled', 'AbortError'))
    signal.addEventListener('abort', abort, { once: true })
    request.then(resolve, reject).finally(() => signal.removeEventListener('abort', abort))
  })
}

const warmedMedia = new Set<string>()
const pendingMedia = new Set<string>()
const mediaQueue: string[] = []
let activeMedia = 0
function drainMediaQueue() {
  while (activeMedia < 4 && mediaQueue.length) {
    const url = mediaQueue.shift()!
    activeMedia += 1
    const image = new Image()
    let completed = false
    let timeout = 0
    const finish = (loaded: boolean) => {
      if (completed) return
      completed = true
      window.clearTimeout(timeout)
      image.onload = image.onerror = null
      pendingMedia.delete(url)
      if (loaded) {
        warmedMedia.add(url)
        if (warmedMedia.size > 256) warmedMedia.delete(warmedMedia.values().next().value!)
      }
      activeMedia -= 1
      drainMediaQueue()
    }
    image.onload = () => finish(true)
    image.onerror = () => finish(false)
    image.decoding = 'async'
    image.fetchPriority = 'low'
    image.referrerPolicy = 'same-origin'
    timeout = window.setTimeout(() => {
      // A stalled speculative request must not hold every preload slot forever.
      // Stop this Image request and leave the URL eligible for a later retry.
      image.removeAttribute('src')
      finish(false)
    }, 15000)
    image.src = url
  }
}

export function warmQuestionMedia(question: QuestionDetail) {
  // Keep both sides of the exercise in the browser's long-lived HTTP cache.
  // QuestionAsset responses are immutable for a year, so this turns the extra
  // transfer into reusable local storage rather than repeated network work.
  const questionAssets = question.question_assets?.length ? question.question_assets : question.assets || []
  const urls = new Set([
    ...questionAssets.map((asset) => asset.url),
    ...(question.answer_assets || []).map((asset) => asset.url),
  ])
  for (const assetUrl of urls) {
    const url = withWorkspacePrefix(assetUrl)
    if (pendingMedia.has(url) || warmedMedia.has(url)) continue
    pendingMedia.add(url)
    mediaQueue.push(url)
  }
  drainMediaQueue()
}

export async function prefetchQuestion(uuid: string | null, query = '') {
  if (!uuid) return
  try {
    const question = await fetchQuestion(uuid, query)
    warmQuestionMedia(question)
    return question
  } catch { /* background prefetch must never block practice */ }
}

export function cachedHeatmap<T>(scope: string): T | null {
  const memory = heatmapCache.get(scope)
  if (memory && Date.now() - memory.savedAt <= 2 * 60 * 1000) return memory.value as T
  const storageKey = scopedKey('heatmap', scope)
  return storageKey ? readStored<T>(storageKey, 2 * 60 * 1000) : null
}

export function storeHeatmap<T>(scope: string, value: T) {
  const entry = { value, savedAt: Date.now() }
  heatmapCache.set(scope, entry)
  const storageKey = scopedKey('heatmap', scope)
  if (storageKey) persist('sessionStorage', storageKey, entry)
}

export function cachedNoteDraft(uuid: string): string | null {
  const storageKey = scopedKey('note-draft', uuid)
  if (!storageKey) return null
  const memory = noteDraftMemory.get(storageKey)
  const ttl = 3 * 24 * 60 * 60 * 1000
  if (memory && Date.now() - memory.savedAt <= ttl) return memory.value
  return readStored<string>(storageKey, ttl)
}

export function storeNoteDraft(uuid: string, value: string) {
  const storageKey = scopedKey('note-draft', uuid)
  if (!storageKey) return false
  noteDraftMemory.set(storageKey, { value, savedAt: Date.now() })
  return persist('localStorage', storageKey, { value, savedAt: Date.now() })
}

export function clearNoteDraft(uuid: string) {
  const storageKey = scopedKey('note-draft', uuid)
  if (!storageKey) return
  noteDraftMemory.set(storageKey, { value: null, savedAt: Date.now() })
  removeStored('localStorage', storageKey)
  removeStored('sessionStorage', storageKey)
}

export function patchQuestionState(uuid: string, patch: Partial<QuestionDetail>) {
  invalidateDerivedCaches()
  // Persisted query variants may not currently be in memory. Drop them before
  // saving patched live entries so a later visit cannot restore the old format.
  for (const key of sessionKeys()) {
    if (key.startsWith(`drill.question-detail.v2.${cacheScope}.${encodeURIComponent(uuid + '?')}`)) removeStored('sessionStorage', key)
  }
  for (const [key, entry] of detailCache) {
    if (!key.startsWith(`${uuid}?`)) continue
    const value = { ...entry.value, ...patch }
    storeQuestion(uuid, key.slice(uuid.length + 1), value)
  }
  // A storage event wakes other tabs. The custom event lets the current tab's
  // list/heatmap widgets refresh from the same database-backed API contract.
  const payload = { uuid, savedAt: Date.now() }
  persist('localStorage', stateEventKey, payload)
  window.dispatchEvent(new CustomEvent('drill:question-state-changed', { detail: payload }))
}
