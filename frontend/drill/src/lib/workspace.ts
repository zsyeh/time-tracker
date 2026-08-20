import { api } from './api'
import type { Catalog, Page, QuestionDetail, QuestionSummary } from '../types'

const catalogKey = 'drill.taxonomy.v1'
const catalogTtl = 7 * 24 * 60 * 60 * 1000
const listTtl = 5 * 60 * 1000
const detailTtl = 24 * 60 * 60 * 1000
const detailLimit = 120

let cacheScope = ''
let memoryCatalog: Catalog | null = null
const listCache = new Map<string, { value: Page<QuestionSummary>; savedAt: number }>()
const detailCache = new Map<string, { value: QuestionDetail; savedAt: number }>()
const detailInflight = new Map<string, Promise<QuestionDetail>>()
const heatmapCache = new Map<string, { value: unknown; savedAt: number }>()

function readStored<T>(key: string, ttl: number): T | null {
  try {
    const stored = JSON.parse(sessionStorage.getItem(key) || localStorage.getItem(key) || 'null')
    if (!stored || Date.now() - Number(stored.savedAt) > ttl) return null
    return stored.value as T
  } catch {
    return null
  }
}

function scopedKey(kind: string, key: string) {
  return cacheScope ? `drill.${kind}.v1.${cacheScope}.${key}` : ''
}

export function configureWorkspaceScope(scope: string) {
  cacheScope = encodeURIComponent(scope)
}

export function cachedCatalog(): Catalog | null {
  if (memoryCatalog) return memoryCatalog
  try {
    const stored = JSON.parse(localStorage.getItem(catalogKey) || 'null')
    if (stored && Date.now() - Number(stored.savedAt) <= catalogTtl) {
      memoryCatalog = stored.value
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
  const value = await api<Catalog>('/api/drill/catalog/')
  memoryCatalog = value
  localStorage.setItem(catalogKey, JSON.stringify({ savedAt: Date.now(), value }))
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
  if (storageKey) sessionStorage.setItem(storageKey, JSON.stringify(entry))
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
  if (storageKey) sessionStorage.setItem(storageKey, JSON.stringify(entry))
}

export function fetchQuestion(uuid: string, query = '', force = false): Promise<QuestionDetail> {
  const key = detailKey(uuid, query)
  if (!force) {
    const cached = cachedQuestion(uuid, query)
    if (cached) return Promise.resolve(cached)
  }
  const existing = detailInflight.get(key)
  if (existing) return existing
  const suffix = query ? `?${query}` : ''
  const request = api<QuestionDetail>(`/api/drill/questions/${uuid}/${suffix}`)
    .then((value) => {
      storeQuestion(uuid, query, value)
      return value
    })
    .finally(() => detailInflight.delete(key))
  detailInflight.set(key, request)
  return request
}

export async function prefetchQuestion(uuid: string | null, query = '') {
  if (!uuid) return
  try {
    const question = await fetchQuestion(uuid, query)
    const firstAsset = question.question_assets?.[0] || question.assets?.[0]
    if (firstAsset) {
      const image = new Image()
      image.decoding = 'async'
      image.src = firstAsset.url
    }
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
  if (storageKey) sessionStorage.setItem(storageKey, JSON.stringify(entry))
}

export function cachedNoteDraft(uuid: string): string | null {
  const storageKey = scopedKey('note-draft', uuid)
  if (!storageKey) return null
  return readStored<string>(storageKey, 3 * 24 * 60 * 60 * 1000)
}

export function storeNoteDraft(uuid: string, value: string) {
  const storageKey = scopedKey('note-draft', uuid)
  if (!storageKey) return
  localStorage.setItem(storageKey, JSON.stringify({ value, savedAt: Date.now() }))
}

export function clearNoteDraft(uuid: string) {
  const storageKey = scopedKey('note-draft', uuid)
  if (!storageKey) return
  localStorage.removeItem(storageKey)
  sessionStorage.removeItem(storageKey)
}

export function patchQuestionState(uuid: string, patch: Partial<QuestionDetail>) {
  heatmapCache.clear()
  if (cacheScope) {
    for (const key of Object.keys(sessionStorage)) {
      if (key.startsWith(`drill.heatmap.v1.${cacheScope}.`)) sessionStorage.removeItem(key)
    }
  }
  for (const [key, entry] of detailCache) {
    if (!key.startsWith(`${uuid}?`)) continue
    const value = { ...entry.value, ...patch }
    storeQuestion(uuid, key.slice(uuid.length + 1), value)
  }
}
