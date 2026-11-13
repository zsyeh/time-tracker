<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, ApiError } from '../lib/api'
import { cachedCatalog, cachedQuestionPage, fetchCatalog, prefetchQuestion, storeQuestionPage } from '../lib/workspace'
import type { Catalog, Page, QuestionSummary } from '../types'
import { useUiPreferences } from '../lib/uiPreferences'
import ExamTypeControls from '../components/ExamTypeControls.vue'
import ExamTypeBadge from '../components/ExamTypeBadge.vue'
import SavedPracticeFilters from '../../../shared/ui/SavedPracticeFilters.vue'
import PracticeFilterPanel from '../components/PracticeFilterPanel.vue'
import PracticePagination from '../components/PracticePagination.vue'
import { buildListContext, previewLocation } from '../lib/listContext'
import { typeText, type TypeStats } from '../lib/examTypes'
import { runtimeWorkspace } from '../lib/runtimePath'
import { usePracticeQuery } from '../composables/usePracticeQuery'
import { clearPracticeFilters, countPracticeFilters, normalizePracticeQuery, serializePracticeQuery, type PracticeQuery } from '../../../shared/search/queryState'
import { learningUserId } from '../../../shared/foregroundTimer'
import { highlightCodepoints } from '../../../shared/search/highlight'
import { uiText } from '../lib/uiText'

const router = useRouter()
const route = useRoute()
const ownerPath = route.path
const rootElement = ref<HTMLElement | null>(null)
const { t } = useUiPreferences()
const catalog = ref<Catalog>({ summary: { imported_count: 0, practiceable_count: 0, outline_count: 0, categories: [] }, coverage: { available: [], missing: [], source_archive_checked: false }, documents: [], topics: [] })
type SearchMatch = { fields: string[]; kind: 'literal'|'alias'|'prefix'|'contains'|'spelling'; excerpt: string; highlights: Array<[number,number]>; coverage: 'text'|'metadata' }
type SearchQuestion = QuestionSummary & { search_match?: SearchMatch }
type SearchPage = Page<SearchQuestion> & { page?: number; page_size?: number; total_pages?: number; type_statistics?: TypeStats; search?: { index_version?: string; version?: string | number; coverage?: { metadata_only_count?: number }; suggestions?: string[]; corrected_terms?: string[] } }
type Candidate = { kind: string; label: string; value: string; documentId: string; reason?: string }
const remoteCandidates = ref<Candidate[]>([])
const remoteQuery = ref('')
const questions = ref<SearchPage | null>(null)
const loading = ref(true)
const error = ref('')
const searchNotice = ref('')
const ready = ref(false)
const filtersOpen = ref(false)
const filterButton = ref<HTMLButtonElement | null>(null)
const searchFocused = ref(false)
const candidateIndex = ref(-1)
const lastQuestionUuid = ref('')
const isEi = runtimeWorkspace === 'ei'
let requestController: AbortController | null = null
let requestSequence = 0
let lastLoadedKey = ''
let prefetchTimer: ReturnType<typeof setTimeout> | undefined
let interactionVersion = 0
let changedByUi = false
let leaving = false
let lastLoadedQuery: PracticeQuery = {}
type ScrollPlan = { kind: 'restore'|'pager'|'results'|'top'; version: number; rowUuid?: string; rowOffset?: number; scrollY?: number; position?: 'top'|'bottom'; offset?: number }
let pendingScroll: ScrollPlan | null = null
let indexVersion = ''
const { applied, draft: search, composing, refresh, apply, input, submitSearch, cancelDraft, compositionStart, compositionEnd } = usePracticeQuery(() => { changedByUi = true; requestSequence += 1; requestController?.abort(); if (prefetchTimer) clearTimeout(prefetchTimer); loading.value = false })
const page = computed(() => Number(applied.value.page) || 1)
const totalPages = computed(() => questions.value?.count ? questions.value.total_pages ?? Math.ceil(questions.value.count / (questions.value.page_size || 24)) : 0)
const queryKey = computed(() => {
  // This protocol flag is added by Question on return, but does not change
  // results. Keep one list cache and scroll context for the same user query.
  const query = { ...applied.value }
  delete query.search_version
  return serializePracticeQuery(query)
})
const statePrefix = computed(() => `learning.practice.view.v2.${runtimeWorkspace}.${learningUserId || 'session'}.`)
const correctedTerms = computed(() => [...new Set(questions.value?.search?.corrected_terms || [])].slice(0, 3))
const filterCount = computed(() => countPracticeFilters(applied.value))
const typeGroup = computed({ get: () => applied.value.type_group || '', set: (value: string) => apply({ type_group: value, exam_type: '' }) })
const localCandidates = computed(() => {
  if (!searchFocused.value) return []
  const query = search.value.trim().toLocaleLowerCase()
  if (!query) return []
  const topics = catalog.value.topics.filter((item) => item.path.toLocaleLowerCase().includes(query)).slice(0, 5).map((item) => ({ kind: 'topic', label: item.path, value: String(item.id), documentId: String(item.document_id) }))
  const books = catalog.value.documents.filter((item) => item.title.toLocaleLowerCase().includes(query)).slice(0, 3).map((item) => ({ kind: 'book', label: item.title, value: String(item.id), documentId: '' }))
  const remote = remoteQuery.value === search.value.trim() ? remoteCandidates.value : []
  const seen = new Set<string>()
  return [...remote, ...topics, ...books].filter((item) => { const key = `${item.kind}:${item.value}`; if (seen.has(key)) return false; seen.add(key); return true }).slice(0, 8)
})
const filterSummary = computed(() => {
  const q = applied.value
  const status: Record<string, string> = { unattempted: '未作答', mastered: '已掌握', review: '待复习', overdue: '已到期' }
  return [catalog.value.documents.find((book) => String(book.id) === q.document)?.title, catalog.value.topics.find((topic) => String(topic.id) === q.topic)?.path,
    catalog.value.summary.categories.find((category) => category.value === q.source_category)?.label,
    q.type_group && ({ small: '小题', large: '大题', short_answer: '简答题', unknown: '未分类' }[q.type_group]),
    q.exam_type, q.status && status[q.status], q.favorite && '收藏', q.review_later && '下次复习', q.marker && '学习标记', q.include_structure && '包含资料目录'].filter(Boolean).map((text) => uiText(String(text)))
})
function applySavedFilters(query:Record<string,string>){search.value=query.q||'';submitSearch();apply({...Object.fromEntries(['from','q','sort','document','topic','source_category','type_group','exam_type','status','favorite','review_later','marker','include_structure','collection','course','material','bucket','tier','kind','combined','state','scope'].map(key=>[key,''])),...query})}
function matchSegments(question: SearchQuestion) { return highlightCodepoints(question.search_match?.excerpt || '', question.search_match?.highlights || []) }
function matchLabel(match: SearchMatch) {
  if (match.coverage !== 'metadata') return ''
  return uiText(match.fields.includes('topic') ? '知识点匹配' : match.fields.includes('book') ? '题册匹配' : '题目信息匹配')
}
function navigationQuery() { return { ...Object.fromEntries(Object.entries(applied.value).filter(([key]) => key !== 'page')), search_version: '2', ...(indexVersion ? { index_version: indexVersion } : {}), ...(page.value > 1 ? { practice_page: String(page.value) } : {}) } }
function navigationQueryString() { return new URLSearchParams(navigationQuery()).toString() }
function readState(key: string) { try { return JSON.parse(sessionStorage.getItem(statePrefix.value + key) || 'null') } catch { return null } }
function persistState() {
  if (!lastLoadedKey && !ready.value) return
  try {
    const rows = [...(rootElement.value?.querySelectorAll<HTMLElement>('.question-row') || [])]
    const visible = (row: HTMLElement) => { const rect = row.getBoundingClientRect(); return rect.bottom > 0 && rect.top < window.innerHeight }
    const anchor = rows.find(row => row.dataset.questionUuid === lastQuestionUuid.value && visible(row)) || rows.find(visible)
    const value = { query: lastLoadedQuery, lastQuestionUuid: lastQuestionUuid.value, scrollY: window.scrollY,
      rowUuid: anchor?.dataset.questionUuid, rowOffset: anchor?.getBoundingClientRect().top, updatedAt: Date.now() }
    sessionStorage.setItem(statePrefix.value + lastLoadedKey, JSON.stringify(value))
    sessionStorage.setItem(statePrefix.value + 'latest', JSON.stringify(value))
  } catch { /* Optional UI restoration must not block browsing. */ }
}
async function placeViewport(plan: ScrollPlan, sequence: number) {
  await nextTick()
  await new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve())))
  if (sequence !== requestSequence || route.path !== ownerPath || plan.version !== interactionVersion) return
  let top = plan.scrollY || 0
  if (plan.kind === 'pager') {
    const pager = rootElement.value?.querySelector<HTMLElement>(`[data-page-position="${plan.position}"]`)
    if (pager) top = window.scrollY + pager.getBoundingClientRect().top - (plan.offset || 0)
  } else if (plan.kind === 'results') {
    const heading = rootElement.value?.querySelector<HTMLElement>('.practice-result-bar')
    if (heading) top = window.scrollY + heading.getBoundingClientRect().top - 16
  } else if (plan.kind === 'restore' && plan.rowUuid) {
    const row = [...(rootElement.value?.querySelectorAll<HTMLElement>('.question-row') || [])].find(row => row.dataset.questionUuid === plan.rowUuid)
    if (row) top = window.scrollY + row.getBoundingClientRect().top - (plan.rowOffset || 0)
  }
  const max = Math.max(0, document.documentElement.scrollHeight - window.innerHeight)
  window.scrollTo({ top: Math.max(0, Math.min(max, Number.isFinite(top) ? top : 0)), behavior: 'auto' })
}

async function loadQuestions(restore = false) {
  if (!ready.value) return
  requestController?.abort()
  if (prefetchTimer) clearTimeout(prefetchTimer)
  requestController = new AbortController()
  const sequence = ++requestSequence
  const key = queryKey.value
  const saved = readState(key)
  const plan: ScrollPlan = pendingScroll || (restore && saved && !changedByUi
    ? { kind: 'restore', version: interactionVersion, rowUuid: saved.rowUuid, rowOffset: saved.rowOffset, scrollY: Number(saved.scrollY) || 0 }
    : { kind: changedByUi ? 'results' : 'top', version: interactionVersion })
  pendingScroll = null; changedByUi = false
  lastLoadedKey = key
  lastLoadedQuery = { ...applied.value }
  lastQuestionUuid.value = saved?.lastQuestionUuid || ''
  const cached = cachedQuestionPage(`${key}&search_version=2`) as SearchPage | null
  if (cached) { questions.value = cached; indexVersion = cached.search?.index_version || ''; void placeViewport(plan, sequence) }
  loading.value = true
  error.value = ''
  try {
    const params = new URLSearchParams(key)
    params.set('search_version', '2')
    if (page.value <= 1) params.delete('index_version')
    const value = await api<SearchPage>(`/api/drill/questions/?${params}`, { signal: requestController.signal })
    if (sequence !== requestSequence) return
    questions.value = value
    indexVersion = value.search?.index_version || ''
    if (applied.value.q && searchFocused.value && (localCandidates.value.length < 3 || value.search?.suggestions?.length || value.search?.corrected_terms?.length)) void loadSuggestions(applied.value.q, sequence, requestController.signal)
    else { remoteCandidates.value = []; remoteQuery.value = '' }
    storeQuestionPage(`${key}&search_version=2`, value)
    await placeViewport(plan, sequence)
    const first = value.results[0]
    if (first) {
      const context = navigationQueryString()
      prefetchTimer = setTimeout(() => {
        if (sequence === requestSequence) void prefetchQuestion(first.uuid, context)
      }, 300)
    }
  } catch (reason) {
    if (sequence !== requestSequence || (reason as Error).name === 'AbortError') return
    if (reason instanceof ApiError && reason.status === 409 && page.value > 1) { searchNotice.value = uiText('题库结果已更新，已返回第 1 页并保留搜索与筛选。'); apply({ page: '1', index_version: '' }, 'replace', false); return }
    error.value = (reason as Error).message
  } finally { if (sequence === requestSequence) loading.value = false }
}
watch([queryKey, refresh], () => { if (ready.value && route.path === ownerPath) { persistState(); candidateIndex.value = -1; void loadQuestions(true) } })
watch(() => route.path, path => { if (path !== ownerPath) { persistState(); leaving = true } }, { flush: 'sync' })
watch(search, () => { candidateIndex.value = -1 })
async function loadSuggestions(query: string, sequence: number, signal: AbortSignal) {
  try {
    const value = await api<{ results: Array<{ kind: 'document' | 'topic' | 'query'; label: string; filters?: { document?: number; topic?: number }; query?: string; reason: string }> }>(`/api/drill/search/suggestions/?q=${encodeURIComponent(query)}&limit=8`, { signal })
    if (sequence !== requestSequence) return
    remoteQuery.value = query
    remoteCandidates.value = value.results.filter((item) => ['document', 'topic', 'query'].includes(item.kind)).map((item) => ({
      kind: item.kind === 'document' ? 'book' : item.kind, label: item.label,
      value: item.kind === 'query' ? item.query || item.label : String(item.kind === 'document' ? item.filters?.document || '' : item.filters?.topic || ''),
      documentId: item.kind === 'topic' ? String(catalog.value.topics.find((topic) => topic.id === item.filters?.topic)?.document_id || '') : '', reason: item.reason,
    }))
  } catch { /* Optional suggestions never block the primary results or catalog suggestions. */ }
}
function changePage(value: number, position: 'top'|'bottom' = 'bottom') {
  if (loading.value || !Number.isSafeInteger(value) || value < 1 || value > totalPages.value || value === page.value) return
  cancelDraft()
  persistState()
  const pager = rootElement.value?.querySelector<HTMLElement>(`[data-page-position="${position}"]`)
  pendingScroll = { kind: 'pager', position, offset: pager?.getBoundingClientRect().top || 0, version: interactionVersion }
  apply({ page: String(value), search_version: '2', index_version: indexVersion }, 'push', false)
}
function changeFilters(value: PracticeQuery) {
  searchNotice.value = ''
  const removed = Object.fromEntries(Object.keys(applied.value).filter((key) => !(key in value)).map((key) => [key, '']))
  apply({ ...removed, ...value })
}
function clearFilters() { changeFilters(clearPracticeFilters(applied.value)) }
function chooseCandidate(candidate: { kind: string; value: string; documentId: string }) {
  if (candidate.kind === 'query') { search.value = candidate.value; searchFocused.value = false; apply({ q: candidate.value }); return }
  search.value = ''
  searchFocused.value = false
  apply({ document: candidate.kind === 'topic' ? candidate.documentId : candidate.value, topic: candidate.kind === 'topic' ? candidate.value : '', q: '' })
}
function focusSearch() {
  searchFocused.value = true
  const query = applied.value.q
  if (query && query === search.value.trim() && localCandidates.value.length < 3 && requestController && !requestController.signal.aborted) void loadSuggestions(query, requestSequence, requestController.signal)
}
function searchKeydown(event: KeyboardEvent) {
  if (composing.value || event.isComposing || event.keyCode === 229) return
  if (event.key === 'Escape') { searchFocused.value = false; candidateIndex.value = -1 }
  else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    if (!localCandidates.value.length) return
    event.preventDefault(); searchFocused.value = true
    candidateIndex.value = (candidateIndex.value + (event.key === 'ArrowDown' ? 1 : -1) + localCandidates.value.length) % localCandidates.value.length
  } else if (event.key === 'Enter') {
    event.preventDefault()
    const candidate = localCandidates.value[candidateIndex.value]
    if (candidate) chooseCandidate(candidate)
    else { searchFocused.value = false; submitSearch() }
  }
}
function openQuestion(uuid: string) { lastQuestionUuid.value = uuid; persistState(); void router.push({ path: `/practice/${uuid}`, query: navigationQuery() }) }
function interactedWithPage() { interactionVersion += 1 }
function previewAll() {
  persistState()
  const query = { ...applied.value }; delete query.page; delete query.index_version; delete query.from
  const selected = questions.value?.results.find(item => item.uuid === lastQuestionUuid.value) || questions.value?.results[0]
  void router.push(previewLocation(buildListContext('practice', query, route.fullPath), undefined, selected?.uuid))
}
onMounted(async () => {
  window.addEventListener('pointerdown', interactedWithPage, { passive: true })
  window.addEventListener('wheel', interactedWithPage, { passive: true })
  window.addEventListener('touchmove', interactedWithPage, { passive: true })
  window.addEventListener('keydown', interactedWithPage)
  try {
    catalog.value = cachedCatalog() || await fetchCatalog()
    if (!queryKey.value) {
      const saved = readState('latest')
      if (saved?.query && Date.now() - Number(saved.updatedAt) < 30 * 86400000) await router.replace({ query: normalizePracticeQuery(saved.query) })
      else {
        // Legacy global state is only imported when its document belongs to this workspace.
        try {
          const old = JSON.parse(localStorage.getItem('drill.practice.state.v1') || 'null')
          if (old?.documentId && catalog.value.documents.some((book) => String(book.id) === String(old.documentId))) {
            const query = normalizePracticeQuery({ document: old.documentId, topic: old.topicId, type_group: old.typeGroup, source_category: old.sourceCategory, q: old.search, unattempted: old.unattempted ? '1' : '', page: old.page })
            await router.replace({ query })
            sessionStorage.setItem(statePrefix.value + serializePracticeQuery(query), JSON.stringify(old))
          }
        } catch { /* Ignore old or restricted browser storage. */ }
      }
    }
    ready.value = true
    await loadQuestions(true)
    void fetchCatalog(true).then((value) => { catalog.value = value }).catch(() => undefined)
  } catch (reason) { error.value = (reason as Error).message; loading.value = false }
})
onUnmounted(() => {
  if (!leaving) persistState(); requestSequence += 1; requestController?.abort(); if (prefetchTimer) clearTimeout(prefetchTimer)
  window.removeEventListener('pointerdown', interactedWithPage); window.removeEventListener('wheel', interactedWithPage); window.removeEventListener('keydown', interactedWithPage)
})
</script>
<template>
  <section ref="rootElement" class="page practice-page">
    <header class="page-header practice-header">
      <div><h1>{{ isEi ? t('electronicInformation') : t('questionBank') }}</h1><p>{{ catalog.summary.practiceable_count.toLocaleString() }} {{ uiText('道可练习题') }} <RouterLink class="practice-progress-link" to="/progress">{{ typeText('学习进度', 'Learning progress') }} →</RouterLink></p></div>
      <button class="preview-all ui-button ui-button--secondary" type="button" :disabled="loading || !questions?.count" @click="previewAll">{{ typeText('全局预览', 'Preview all') }}</button>
      <button class="primary-action" :disabled="loading || !(lastQuestionUuid || questions?.results.length)" @click="openQuestion(lastQuestionUuid || questions!.results[0].uuid)">{{ lastQuestionUuid ? t('resumeLast') : t('openNext') }} <span aria-hidden="true">→</span></button>
    </header>
    <div class="practice-toolbar">
      <div class="practice-search" @focusout="!($event.currentTarget as HTMLElement).contains($event.relatedTarget as Node) && (searchFocused = false)">
        <label class="sr-only" for="practice-search">{{ uiText('搜索题库') }}</label>
        <input id="practice-search" v-model="search" type="search" role="combobox" autocomplete="off" :aria-expanded="Boolean(localCandidates.length)" aria-controls="practice-suggestions" :aria-activedescendant="candidateIndex >= 0 ? `practice-suggestion-${candidateIndex}` : undefined" :placeholder="uiText('搜索题目、题册或知识点')" @focus="focusSearch" @input="input" @compositionstart="compositionStart" @compositionend="compositionEnd" @keydown="searchKeydown" />
        <div v-if="localCandidates.length" id="practice-suggestions" class="practice-suggestions" role="listbox" :aria-label="uiText('搜索建议')"><button v-for="(candidate, index) in localCandidates" :id="`practice-suggestion-${index}`" :key="`${candidate.kind}-${candidate.value}`" role="option" :aria-selected="index === candidateIndex" type="button" @pointerdown.prevent @click="chooseCandidate(candidate)"><small>{{ candidate.kind === 'query' ? uiText('搜索术语') : candidate.kind === 'topic' ? uiText('筛选知识点') : uiText('筛选题册') }}</small><span>{{ candidate.label }}</span></button></div>
      </div>
      <button ref="filterButton" class="filter-trigger" type="button" :aria-expanded="filtersOpen" aria-haspopup="dialog" @click="filtersOpen = !filtersOpen">{{ uiText('筛选') }}<span v-if="filterCount"> ({{ filterCount }})</span></button>
      <label class="practice-sort"><span class="sr-only">{{ uiText('排序') }}</span><select :value="applied.sort || (applied.q ? 'relevance' : 'source')" @change="apply({ sort: ($event.target as HTMLSelectElement).value })"><option v-if="applied.q" value="relevance">{{ uiText('相关性') }}</option><option value="source">{{ uiText('题册顺序') }}</option></select></label>
    </div>
    <div class="practice-result-bar"><label class="quick-unattempted"><input type="checkbox" :checked="applied.status === 'unattempted'" @change="apply({ status: ($event.target as HTMLInputElement).checked ? 'unattempted' : '' })" />{{ uiText('仅未作答') }}</label><span role="status" aria-live="polite">{{ questions?.count ?? 0 }} {{ uiText('道题') }}<span v-if="loading"> · {{ uiText('正在更新…') }}</span></span></div>
    <p v-if="applied.q" class="search-order-note">{{ uiText("排序只影响结果列表，练习仍按题册顺序。") }}</p>
    <div v-if="filterSummary.length" class="filter-summary"><span>{{ filterSummary.join(' · ') }}</span><button type="button" @click="clearFilters">{{ uiText('清除筛选') }}</button></div>
    <div class="practice-extras"><details class="practice-type-overview"><summary>{{ uiText('题型概览') }}</summary><ExamTypeControls v-model="typeGroup" :stats="questions?.type_statistics" @practice="typeGroup = 'small'" /></details>
    <div class="saved-filter-entry"><SavedPracticeFilters :workspace="isEi?'ei':'drill'" :query="applied" @apply="applySavedFilters"/></div></div>
    <PracticeFilterPanel :open="filtersOpen" :anchor="filterButton" :model-value="applied" :catalog="catalog" @update:open="filtersOpen = $event" @update:model-value="changeFilters" />
    <p v-if="applied.q && correctedTerms.length" class="search-expansion" role="status">{{ typeText('同时匹配', 'Also matching') }}：{{ correctedTerms.join('、') }}</p>
    <p v-if="searchNotice" class="search-notice" role="status">{{ searchNotice }}</p>
    <p v-if="error" class="error-state" role="alert">{{ uiText(error) }} <button type="button" @click="loadQuestions()">{{ uiText('重试') }}</button></p>
    <PracticePagination v-if="questions" :page="page" :total-pages="totalPages" :count="questions.count" :loading="loading" position="top" @change="changePage" />
    <div v-if="!error" class="question-list practice-results" :aria-busy="loading">
      <template v-if="loading && !questions"><div v-for="index in 8" :key="index" class="practice-skeleton" aria-hidden="true"><span /><span /></div></template>
      <RouterLink v-for="question in questions?.results" :key="question.uuid" :to="{ path: `/practice/${question.uuid}`, query: navigationQuery() }" :data-type-group="question.type_group" :data-question-uuid="question.uuid" class="question-row" @pointerenter="prefetchQuestion(question.uuid, navigationQueryString())" @click="lastQuestionUuid = question.uuid; persistState()">
        <span class="question-index">{{ String(question.question_order).padStart(4, '0') }}</span>
        <span class="question-copy"><strong>{{ question.display_label || `${uiText('题目')} ${question.question_order}` }}</strong><small><ExamTypeBadge :type="question.question_type" :group="question.type_group" /> · {{ question.document }} · {{ question.topic || uiText('未分类') }} · {{ question.source_category_label }}<em v-if="question.record_kind === 'grouped'"> {{ uiText('· 组合题摘录') }}</em><em v-if="question.pdf_pages"> · PDF {{ question.pdf_pages.question }}/{{ question.pdf_pages.answer }}/{{ question.pdf_pages.paired }}</em></small><p v-if="applied.q && question.search_match?.excerpt" class="practice-search-excerpt"><span v-if="question.search_match.coverage === 'metadata'" class="search-match-label">{{ matchLabel(question.search_match) }} · </span><template v-for="(part, index) in matchSegments(question)" :key="index"><mark v-if="part.match">{{ part.text }}</mark><template v-else>{{ part.text }}</template></template></p></span>
        <span class="practice-state" :class="question.review_overdue ? 'is-overdue' : `is-${question.state}`">{{ question.review_overdue ? uiText('已到期') : question.state === 'mastered' ? uiText('已掌握') : question.state === 'review' ? uiText('待复习') : uiText('未作答') }}<small v-if="question.attempt_count"> · {{ question.attempt_count }}</small></span>
        <span class="row-arrow" aria-hidden="true">→</span>
      </RouterLink>
      <div v-if="!loading && !questions?.results.length" class="empty-state"><strong>{{ uiText('没有符合条件的题目') }}</strong><p>{{ applied.q ? `“${applied.q}” · ` : '' }}{{ uiText('试试其他关键词或减少筛选条件。扫描题可能仅有题册、知识点等信息可搜索。') }}</p><button v-for="candidate in remoteCandidates.filter((item) => item.kind === 'query')" :key="candidate.value" type="button" @click="chooseCandidate(candidate)">{{ uiText('试试') }} {{ candidate.label }}</button><button v-if="filterCount" type="button" @click="clearFilters">{{ uiText('清除筛选') }}</button><button v-if="applied.q" type="button" @click="search = ''; submitSearch()">{{ uiText('清除搜索') }}</button></div>
    </div>
    <PracticePagination v-if="questions" :page="page" :total-pages="totalPages" :count="questions.count" :loading="loading" position="bottom" @change="changePage" />
    <details v-if="catalog.coverage.missing.length || catalog.summary.outline_count" class="practice-source-details"><summary>{{ uiText('题库资料说明') }}</summary><p>{{ catalog.summary.outline_count }} {{ uiText('条目录记录未作为题目展示。') }}</p><p v-if="catalog.coverage.missing.length">{{ uiText('资料缺失') }}：{{ catalog.coverage.missing.join(', ') }}</p></details>
  </section>
</template>
<style scoped>
.practice-header .preview-all { min-height:44px; margin-left:auto; padding:8px 12px; flex:none; }
.practice-header > .primary-action { flex:none; }
@media(max-width:600px) { .practice-header { flex-wrap:wrap; } .practice-header > div { flex:1 1 100%; } .practice-header .preview-all { margin-left:0; } }

.practice-extras{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;align-items:start;margin-bottom:4px}.saved-filter-entry{display:flex;justify-content:flex-end;margin:0;white-space:nowrap}.saved-filter-entry :deep(>button){font-size:12px;min-height:36px;padding:4px 8px}
.practice-page { min-width:0; } .search-order-note { margin:0 0 8px; font-size:12px; color:var(--text-secondary); line-height:1.5; } .search-notice { margin:12px 0; color:var(--text-secondary); font-size:13px; line-height:1.5; } .practice-header h1 { margin:0; } .practice-header p { margin:8px 0 0; font-size:13px; } .practice-progress-link { margin-left:16px; color:var(--accent-ink); text-decoration:none; }
.practice-toolbar { display:grid;grid-template-columns:minmax(0,1fr) auto minmax(100px,140px); gap:8px; align-items:center; margin:12px 0 4px; } .practice-search { position:relative; flex:1; min-width:0; } .practice-search input { width:100%; min-height:44px; background:var(--surface-subtle); color:var(--text-primary); border:1px solid var(--border-control); border-radius:8px; padding:10px 12px; font-size:16px; }
.filter-trigger, .practice-sort select { white-space:nowrap; min-height:44px; padding:8px 12px; font-size:14px; color:var(--text-primary); background:var(--surface-subtle); border:0; border-radius:6px; cursor:pointer; } .practice-sort select { background:transparent; padding-right:4px; max-width:100%; width:100%; min-width:0; }
.practice-result-bar { display:flex; align-items:center; justify-content:space-between; gap:12px; min-height:44px; font-size:13px; color:var(--text-secondary); } .quick-unattempted { display:flex; align-items:center; gap:8px; min-height:44px; cursor:pointer; } input[type=checkbox] { width:18px; height:18px; accent-color:var(--accent-solid); }
.practice-suggestions { position:absolute; top:calc(100% + 4px); width:100%; z-index:20; border:1px solid var(--border-subtle); border-radius:8px; padding:4px; background:var(--surface-elevated); max-height:320px; overflow:auto; } .practice-suggestions button { display:flex; flex-direction:column; gap:4px; text-align:left; min-height:52px; width:100%; border:0; padding:8px; color:var(--text-primary); background:transparent; border-radius:4px; } .practice-suggestions button:hover, .practice-suggestions button[aria-selected=true] { background:var(--surface-selected); } .practice-suggestions small { color:var(--text-secondary); font-size:12px; }
.filter-summary { display:flex; align-items:start; gap:12px; margin-bottom:12px; font-size:13px; color:var(--text-secondary); } .filter-summary span { display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; } .filter-summary button { flex:none; background:transparent; color:var(--accent-ink); border:0; padding:0; font:inherit; cursor:pointer; }
.practice-type-overview { margin:0;min-width:0; } .practice-type-overview summary, .practice-source-details summary { min-height:36px; display:flex; align-items:center; color:var(--text-secondary); cursor:pointer; font-size:13px; list-style:none; } .practice-type-overview summary::after, .practice-source-details summary::after { content:'⌄'; margin-left:8px; } .practice-results { border:0; border-top:1px solid var(--border-subtle); border-radius:0; background:transparent; } .practice-results .question-row { grid-template-columns:44px minmax(0,1fr) auto 16px; text-decoration:none; min-height:76px; border:0; border-bottom:1px solid var(--border-subtle); border-radius:0; color:var(--text-primary); padding:12px 8px; background:transparent; } .practice-results .question-row:hover { background:var(--surface-hover); } .question-copy { min-width:0; } .practice-search-excerpt { display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; margin:4px 0 0; font-size:13px; line-height:1.5; color:var(--text-secondary); overflow-wrap:anywhere; } .practice-search-excerpt mark { color:var(--accent-ink); background:var(--accent-soft); border-radius:2px; } .search-match-label { font-size:12px; } .question-copy strong { font-size:14px; font-weight:600; } .question-copy small { font-size:12px; line-height:1.5; } .practice-state { color:var(--text-secondary); font-size:12px; white-space:nowrap; } .practice-state.is-mastered { color:var(--success); } .practice-state.is-review,.practice-state.is-overdue { color:var(--warning); } .practice-state small { color:var(--text-secondary); } .question-index { font-variant-numeric:tabular-nums; font-size:12px; }
.practice-skeleton { height:76px; border-bottom:1px solid var(--border-subtle); padding:16px 8px; display:grid; gap:8px; } .practice-skeleton span { height:12px; background:var(--surface-subtle); width:70%; border-radius:4px; } .practice-skeleton span+span { width:50%; } .practice-source-details { margin-top:24px; font-size:12px; color:var(--text-secondary); } .empty-state strong { font-size:16px; } .empty-state p { font-size:14px; } .sr-only { position:absolute; width:1px; height:1px; padding:0; margin:-1px; overflow:hidden; clip:rect(0,0,0,0); white-space:nowrap; border:0; }
@media(max-width:600px) { .practice-header { align-items:start; gap:12px; } .practice-header h1 { font-size:24px; } .practice-header .primary-action { min-height:44px; padding:8px 12px; font-size:13px; } .practice-toolbar { grid-template-columns:minmax(0,1fr) auto minmax(90px,110px);margin-top:12px; } .practice-sort { margin-left:auto; } .practice-sort select { min-height:36px; font-size:13px; } .practice-result-bar { min-height:40px; } .practice-results .question-row { grid-template-columns:32px minmax(0,1fr) auto; gap:8px; padding:12px 0; } .row-arrow { display:none; } .practice-state { font-size:12px; } .practice-progress-link { display:block; margin:4px 0 0; } .question-copy small { display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; } }
.search-expansion { margin: 0 0 12px; color: var(--text-secondary); font-size: 13px; }
</style>
