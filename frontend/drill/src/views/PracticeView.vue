<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../lib/api'
import { cachedCatalog, cachedQuestionPage, fetchCatalog, prefetchQuestion, storeQuestionPage } from '../lib/workspace'
import type { Catalog, Page, QuestionSummary } from '../types'

const router = useRouter()
const route = useRoute()
const catalog = ref<Catalog>({
  summary: { imported_count: 0, practiceable_count: 0, outline_count: 0, categories: [] },
  coverage: { available: [], missing: [], source_archive_checked: false },
  documents: [],
  topics: [],
})
const questions = ref<Page<QuestionSummary> | null>(null)
const loading = ref(true)
const error = ref('')
const documentId = ref('')
const topicId = ref('')
const search = ref('')
const sourceCategory = ref('')
const unattempted = ref(false)
const markerCode = ref('')
const page = ref(1)
const lastQuestionUuid = ref('')
let searchTimer = 0
let requestController: AbortController | null = null
let requestSequence = 0
let restoring = true
const stateKey = 'drill.practice.state.v1'
const searchFocused = ref(false)
const isEi = location.hostname.toLowerCase().startsWith('ei.')

const topics = computed(() => catalog.value.topics.filter((topic) => (
  !documentId.value || topic.document_id === Number(documentId.value)
)))
const topicGroups = computed(() => catalog.value.documents.map((document) => ({
  document,
  topics: topics.value.filter((topic) => topic.document_id === document.id),
})).filter((group) => group.topics.length))
const categoryOptions = computed(() => catalog.value.summary.categories.filter((item) => item.count > 0))
const normalizedSearch = computed(() => search.value.trim().toLocaleLowerCase())
const localCandidates = computed(() => {
  if (!searchFocused.value) return []
  const query = normalizedSearch.value
  const topics = catalog.value.topics
    .filter((item) => !query || item.path.toLocaleLowerCase().includes(query))
    .slice(0, 6)
    .map((item) => ({ kind: 'Topic', label: item.path, value: String(item.id), documentId: String(item.document_id) }))
  const books = catalog.value.documents
    .filter((item) => !query || item.title.toLocaleLowerCase().includes(query))
    .slice(0, 4)
    .map((item) => ({ kind: 'Book', label: item.title, value: String(item.id), documentId: '' }))
  return [...topics, ...books].slice(0, 8)
})

function queryParams() {
  const params = new URLSearchParams({ page: String(page.value) })
  if (documentId.value) params.set('document', documentId.value)
  if (topicId.value) params.set('topic', topicId.value)
  if (search.value.trim().length >= 2) params.set('q', search.value.trim())
  if (sourceCategory.value) params.set('source_category', sourceCategory.value)
  if (unattempted.value) params.set('unattempted', '1')
  if (markerCode.value) params.set('marker', markerCode.value)
  return params
}

function navigationQuery() {
  return Object.fromEntries([...queryParams()].filter(([key]) => key !== 'page'))
}

function navigationQueryString() {
  return new URLSearchParams(navigationQuery()).toString()
}

function closeCandidatesLater() {
  window.setTimeout(() => { searchFocused.value = false }, 150)
}

async function loadQuestions() {
  requestController?.abort()
  requestController = new AbortController()
  const sequence = ++requestSequence
  const params = queryParams()
  const cacheKey = params.toString()
  const cached = cachedQuestionPage(cacheKey)
  if (cached) questions.value = cached
  loading.value = !cached
  error.value = ''
  try {
    const value = await api<Page<QuestionSummary>>(`/api/drill/questions/?${params}`, { signal: requestController.signal })
    if (sequence !== requestSequence) return
    questions.value = value
    storeQuestionPage(cacheKey, value)
  } catch (reason) {
    if ((reason as Error).name !== 'AbortError') error.value = (reason as Error).message
  } finally {
    if (sequence === requestSequence) loading.value = false
  }
}

function persistState() {
  localStorage.setItem(stateKey, JSON.stringify({
    documentId: documentId.value, topicId: topicId.value, sourceCategory: sourceCategory.value,
    unattempted: unattempted.value, search: search.value, page: page.value,
    lastQuestionUuid: lastQuestionUuid.value, scrollY: window.scrollY, updatedAt: Date.now(),
  }))
}

function filtersChanged() {
  if (restoring) return
  page.value = 1
  persistState()
  void loadQuestions()
}

function searchChanged() {
  window.clearTimeout(searchTimer)
  requestController?.abort()
  persistState()
  if (search.value.trim().length === 1) {
    loading.value = false
    return
  }
  searchTimer = window.setTimeout(filtersChanged, 400)
}

watch(documentId, () => {
  if (!topics.value.some((topic) => String(topic.id) === topicId.value)) topicId.value = ''
  filtersChanged()
})
watch([topicId, sourceCategory, unattempted, markerCode], filtersChanged)
watch(page, persistState)
watch(search, persistState)

function chooseCandidate(candidate: { kind: string; value: string; documentId: string }) {
  if (candidate.kind === 'Topic') {
    documentId.value = candidate.documentId
    topicId.value = candidate.value
  } else {
    documentId.value = candidate.value
    topicId.value = ''
  }
  search.value = ''
  searchFocused.value = false
}

function openQuestion(uuid: string) {
  lastQuestionUuid.value = uuid
  persistState()
  void router.push({ path: `/practice/${uuid}`, query: navigationQuery() })
}

onMounted(async () => {
  try {
    const saved = JSON.parse(localStorage.getItem(stateKey) || 'null')
    if (saved && Date.now() - Number(saved.updatedAt || 0) < 1000 * 60 * 60 * 24 * 30) {
      documentId.value = saved.documentId || ''
      topicId.value = saved.topicId || ''
      sourceCategory.value = saved.sourceCategory || ''
      unattempted.value = Boolean(saved.unattempted)
      search.value = saved.search || ''
      page.value = Number(saved.page) || 1
      lastQuestionUuid.value = saved.lastQuestionUuid || ''
    }
    if (route.query.document !== undefined) documentId.value = String(route.query.document || '')
    if (route.query.topic !== undefined) topicId.value = String(route.query.topic || '')
    if (route.query.source_category !== undefined) sourceCategory.value = String(route.query.source_category || '')
    if (route.query.q !== undefined) search.value = String(route.query.q || '')
    if (route.query.marker !== undefined) markerCode.value = String(route.query.marker || '')
    restoring = false
    catalog.value = cachedCatalog() || await fetchCatalog()
    await loadQuestions()
    void fetchCatalog(true).then((value) => { catalog.value = value }).catch(() => undefined)
    const first = questions.value?.results[0]
    if (first) window.setTimeout(() => void prefetchQuestion(first.uuid, navigationQueryString()), 300)
    requestAnimationFrame(() => window.scrollTo({ top: Number(saved?.scrollY || 0), behavior: 'auto' }))
  } catch (reason) {
    error.value = (reason as Error).message
    loading.value = false
  }
})
onUnmounted(() => {
  requestController?.abort()
  window.clearTimeout(searchTimer)
  persistState()
})
</script>

<template>
  <section class="page practice-page">
    <header class="page-header">
      <div><span class="eyebrow">{{ isEi ? '892 FOUNDATION BANK' : 'CLEANED QUESTION INDEX' }}</span><h1>{{ isEi ? 'Electronic information practice.' : 'Know what you are practising.' }}</h1><p>{{ catalog.summary.practiceable_count.toLocaleString() }} practice records. {{ catalog.summary.outline_count.toLocaleString() }} source-outline rows are hidden.</p></div>
      <button v-if="lastQuestionUuid || questions?.results.length" class="primary-action" @pointerenter="prefetchQuestion(lastQuestionUuid || questions?.results[0]?.uuid || null, navigationQueryString())" @click="openQuestion(lastQuestionUuid || questions!.results[0].uuid)">{{ lastQuestionUuid ? 'Resume last question' : 'Open next question' }} <b>→</b></button>
    </header>

    <aside v-if="!isEi" class="collection-credit"><strong>THANKS TO CXY</strong><span>All question-bank source material was collected and organized by Bilibili creator cxy (澄潇宇). PDF authorship is shown separately when available.</span></aside>
    <aside v-else class="collection-credit"><strong>892 · EI</strong><span>156 foundational examples and 60 short-answer questions imported from the owner-provided Markdown bank. Formulae are rendered from the original LaTeX.</span></aside>

    <div class="taxonomy-grid">
      <button :class="{ active: sourceCategory === '' }" @click="sourceCategory = ''"><span>ALL PRACTICE</span><strong>{{ catalog.summary.practiceable_count.toLocaleString() }}</strong><small>cleaned records</small></button>
      <button v-for="item in categoryOptions" :key="item.value" :class="[`category-${item.value}`, { active: sourceCategory === item.value }]" @click="sourceCategory = item.value"><span>{{ item.label.toUpperCase() }}</span><strong>{{ item.count.toLocaleString() }}</strong><small>{{ item.value === 'past_exam' ? 'verified official source' : 'source-labelled records' }}</small></button>
    </div>

    <aside v-if="catalog.coverage.missing.length" class="source-gap"><strong>SOURCE GAP</strong><span>{{ catalog.coverage.missing.join(', ') }} is not present in <code>Downloads.7z</code>. It is not hidden by a filter.</span></aside>

    <aside v-if="markerCode" class="marker-filter"><span>MARKER</span><strong>{{ markerCode === 'overconfident' ? 'Overconfident' : markerCode === 'concept_gap' ? 'Concept Gap' : markerCode === 'rusty' ? 'Rusty' : 'Forgotten' }}</strong><button type="button" @click="markerCode = ''">Clear</button></aside>

    <div class="filter-panel">
      <label class="search-field"><span>SEARCH</span><input v-model="search" placeholder="Source, topic, or question text" @focus="searchFocused = true" @blur="closeCandidatesLater" @input="searchChanged" /><div v-if="localCandidates.length" class="local-candidates"><button v-for="candidate in localCandidates" :key="`${candidate.kind}-${candidate.value}`" type="button" @mousedown.prevent="chooseCandidate(candidate)"><small>LOCAL {{ candidate.kind.toUpperCase() }}</small><strong>{{ candidate.label }}</strong></button></div></label>
      <label><span>BOOK</span><select v-model="documentId"><option value="">All books</option><option v-for="item in catalog.documents" :key="item.id" :value="item.id">{{ item.title }} · {{ item.question_count }}</option></select></label>
      <label><span>TOPIC PATH</span><select v-model="topicId"><option value="">All topics</option><optgroup v-for="group in topicGroups" :key="group.document.id" :label="group.document.title"><option v-for="item in group.topics" :key="item.id" :value="item.id">{{ item.path }} · {{ item.question_count }}</option></optgroup></select></label>
      <div class="toggle-row"><button :class="{ active: unattempted }" @click="unattempted = !unattempted">Unattempted</button></div>
    </div>

    <div class="result-meta"><span>{{ questions?.count ?? 0 }} PRACTICE RECORDS</span><span class="state-legend"><i class="status-unattempted" /> NOT STARTED <i class="status-mastered" /> MASTERED <i class="status-review" /> REVIEW</span><span v-if="loading">LOADING…</span></div>
    <p v-if="error" class="error-state">{{ error }}</p>
    <div v-else class="question-list" :class="{ loading }">
      <button v-for="question in questions?.results" :key="question.uuid" class="question-row" @pointerenter="prefetchQuestion(question.uuid, navigationQueryString())" @pointerdown="prefetchQuestion(question.uuid, navigationQueryString())" @click="openQuestion(question.uuid)">
        <span class="question-index">{{ String(question.question_order).padStart(4, '0') }}</span>
        <span class="question-copy"><strong>{{ question.display_label || `Question ${question.question_order}` }}</strong><small>{{ question.document }} · {{ question.topic || 'General' }}<em v-if="question.record_kind === 'grouped'"> · grouped extract</em></small></span>
        <span class="source-badge" :class="`category-${question.source_category}`">{{ question.source_category_label }}</span>
        <span class="attempt-mark" :class="`status-${question.state}`" :title="`${question.state}; ${question.attempt_count} recorded attempts`">{{ question.attempt_count || '' }}</span>
        <b class="row-arrow">→</b>
      </button>
      <div v-if="!loading && !questions?.results.length" class="empty-state">No questions match these filters.</div>
    </div>
    <footer v-if="questions && (questions.previous || questions.next)" class="pager"><button :disabled="!questions.previous" @click="page--; loadQuestions()">← Previous</button><span>PAGE {{ page }}</span><button :disabled="!questions.next" @click="page++; loadQuestions()">Next →</button></footer>
  </section>
</template>
