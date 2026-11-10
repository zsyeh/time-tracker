<script setup lang="ts">
import { uiText } from '../lib/uiText'
import { computed, defineAsyncComponent, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../lib/api'
import { cachedCatalog, cachedQuestionPage, fetchCatalog, prefetchQuestion, storeQuestionPage } from '../lib/workspace'
import type { Catalog, Page, QuestionSummary } from '../types'
import { useUiPreferences } from '../lib/uiPreferences'
import ExamTypeControls from '../components/ExamTypeControls.vue'
import ExamTypeBadge from '../components/ExamTypeBadge.vue'
import { formatColours, type TypeStats } from '../lib/examTypes'
import { runtimeWorkspace } from '../lib/runtimePath'

const PracticeTrendPanel = defineAsyncComponent(() => import('../components/PracticeTrendPanel.vue'))

const router = useRouter()
const { t } = useUiPreferences()
const route = useRoute()
const catalog = ref<Catalog>({
  summary: { imported_count: 0, practiceable_count: 0, outline_count: 0, categories: [] },
  coverage: { available: [], missing: [], source_archive_checked: false },
  documents: [],
  topics: [],
})
const questions = ref<(Page<QuestionSummary> & { type_statistics?: TypeStats }) | null>(null)
const loading = ref(true)
const error = ref('')
const documentId = ref('')
const topicId = ref('')
const typeGroup = ref('')
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
const isEi = runtimeWorkspace === 'ei'

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
  if (route.query.collection) {
    for (const key of ['collection', 'bucket', 'tier', 'kind', 'combined', 'state', 'material', 'course', 'from']) {
      if (typeof route.query[key] === 'string' && route.query[key]) params.set(key, String(route.query[key]))
    }
  }
  if (typeGroup.value) params.set('type_group', typeGroup.value)
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
    typeGroup: typeGroup.value, documentId: documentId.value, topicId: topicId.value, sourceCategory: sourceCategory.value,
    unattempted: unattempted.value, search: search.value, page: page.value,
    lastQuestionUuid: lastQuestionUuid.value, scrollY: window.scrollY, updatedAt: Date.now(),
  }))
}

function filtersChanged() {
  if (restoring) return
  page.value = 1
  lastQuestionUuid.value = ''
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
watch([typeGroup, topicId, sourceCategory, unattempted, markerCode], filtersChanged)
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
      typeGroup.value = saved.typeGroup || ''
      documentId.value = saved.documentId || ''
      topicId.value = saved.topicId || ''
      sourceCategory.value = saved.sourceCategory || ''
      unattempted.value = Boolean(saved.unattempted)
      search.value = saved.search || ''
      page.value = Number(saved.page) || 1
      lastQuestionUuid.value = saved.lastQuestionUuid || ''
    }
    if (route.query.type_group !== undefined) {
      typeGroup.value = String(route.query.type_group || '')
      documentId.value = ''; topicId.value = ''; sourceCategory.value = ''; search.value = ''; page.value = 1
      lastQuestionUuid.value = ''
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
  <section :class="{ 'exam-type-colours': formatColours }" class="page practice-page">
    <header class="page-header">
      <div><span class="eyebrow">{{ isEi ? t('foundationBank') : t('questionIndex') }}</span><h1>{{ isEi ? t('electronicInformation') : t('questionBank') }}</h1><p>{{ uiText("共") }} {{ catalog.summary.practiceable_count.toLocaleString() }} {{ uiText("道可练习题；另有") }} {{ catalog.summary.outline_count.toLocaleString() }} {{ uiText("条资料目录记录未作为题目展示。") }}</p></div>
      <button v-if="lastQuestionUuid || questions?.results.length" class="primary-action" :disabled="loading" @pointerenter="prefetchQuestion(lastQuestionUuid || questions?.results[0]?.uuid || null, navigationQueryString())" @click="openQuestion(lastQuestionUuid || questions!.results[0].uuid)">{{ lastQuestionUuid ? t('resumeLast') : t('openNext') }} <b>→</b></button>
    </header>

    <PracticeTrendPanel />

    <aside v-if="!isEi" class="collection-credit"><strong>{{ uiText("感谢 CXY") }}</strong><span>{{ uiText("题库源资料由 Bilibili 创作者 cxy（澄潇宇）收集整理；可确认时会另行标注 PDF 作者。") }}</span></aside>
    <aside v-else class="collection-credit"><strong>892 · EI</strong><span>{{ uiText("已从用户提供的 Markdown 题库导入基础例题与简答题，公式按原始 LaTeX 渲染。") }}</span></aside>

    <div class="taxonomy-grid">
      <button :class="{ active: sourceCategory === '' }" @click="sourceCategory = ''"><span>{{ uiText("全部练习") }}</span><strong>{{ catalog.summary.practiceable_count.toLocaleString() }}</strong><small>{{ uiText("已清洗题目") }}</small></button>
      <button v-for="item in categoryOptions" :key="item.value" :class="[`category-${item.value}`, { active: sourceCategory === item.value }]" @click="sourceCategory = item.value"><span>{{ uiText(item.label) }}</span><strong>{{ item.count.toLocaleString() }}</strong><small>{{ item.value === 'past_exam' ? uiText("已核验正式来源") : uiText("按资料来源标记") }}</small></button>
    </div>

    <aside v-if="catalog.coverage.missing.length" class="source-gap"><strong>{{ uiText("资料缺失") }}</strong><span><code>{{ catalog.coverage.missing.join(', ') }}</code> {{ uiText("不在 Downloads.7z 中，并非被筛选条件隐藏。") }}</span></aside>

    <aside v-if="markerCode" class="marker-filter"><span>{{ uiText("学习标记") }}</span><strong>{{ markerCode === 'overconfident' ? uiText("过度自信") : markerCode === 'concept_gap' ? uiText("概念缺口") : markerCode === 'rusty' ? uiText("生疏") : uiText("遗忘") }}</strong><button type="button" @click="markerCode = ''">{{ uiText("清除") }}</button></aside>

    <div class="filter-panel">
      <label class="search-field"><span>{{ uiText("搜索") }}</span><input v-model="search" :placeholder="uiText('资料、知识点或题目文字')" @focus="searchFocused = true" @blur="closeCandidatesLater" @input="searchChanged" /><div v-if="localCandidates.length" class="local-candidates"><button v-for="candidate in localCandidates" :key="`${candidate.kind}-${candidate.value}`" type="button" @mousedown.prevent="chooseCandidate(candidate)"><small>{{ uiText("本地匹配 ·") }} {{ candidate.kind }}</small><strong>{{ candidate.label }}</strong></button></div></label>
      <label><span>{{ uiText("题册") }}</span><select v-model="documentId"><option value="">{{ uiText("全部题册") }}</option><option v-for="item in catalog.documents" :key="item.id" :value="item.id">{{ item.title }} · {{ item.question_count }}</option></select></label>
      <label><span>{{ uiText("知识点") }}</span><select v-model="topicId"><option value="">{{ uiText("全部知识点") }}</option><optgroup v-for="group in topicGroups" :key="group.document.id" :label="group.document.title"><option v-for="item in group.topics" :key="item.id" :value="item.id">{{ item.path }} · {{ item.question_count }}</option></optgroup></select></label>
      <div class="toggle-row"><button :class="{ active: unattempted }" @click="unattempted = !unattempted">{{ uiText("仅看未作答") }}</button></div>
    </div>

    <ExamTypeControls v-model="typeGroup" :stats="questions?.type_statistics" @practice="typeGroup = 'small'" />
    <div class="result-meta"><span>{{ questions?.count ?? 0 }} {{ uiText("道题") }}</span><span class="state-legend"><i class="status-unattempted" /> {{ uiText("未开始") }} <i class="status-mastered" /> {{ uiText("已掌握") }} <i class="status-review" /> {{ uiText("待复习") }} <i class="status-overdue" /> {{ uiText("已到期") }}</span><span v-if="loading">{{ uiText("正在加载…") }}</span></div>
    <p v-if="error" class="error-state">{{ uiText(error) }}</p>
    <div v-else class="question-list" :class="{ loading }">
      <button v-for="question in questions?.results" :key="question.uuid" :data-type-group="question.type_group" :disabled="loading" class="question-row" @pointerenter="prefetchQuestion(question.uuid, navigationQueryString())" @pointerdown="prefetchQuestion(question.uuid, navigationQueryString())" @click="openQuestion(question.uuid)">
        <span class="question-index">{{ String(question.question_order).padStart(4, '0') }}</span>
        <span class="question-copy"><strong>{{ question.display_label || `${uiText("题目")} ${question.question_order}` }}</strong><small><ExamTypeBadge :type="question.question_type" :group="question.type_group" /> · {{ question.document }} · {{ question.topic || uiText("未分类") }}<em v-if="question.record_kind === 'grouped'"> {{ uiText("· 组合题摘录") }}</em><em v-if="question.pdf_pages"> {{ uiText("· PDF 题") }} {{ question.pdf_pages.question }} {{ uiText("/ 答") }} {{ question.pdf_pages.answer }} {{ uiText("/ 对照") }} {{ question.pdf_pages.paired }} {{ uiText("页") }}</em></small></span>
        <span class="source-badge" :class="`category-${question.source_category}`">{{ question.source_category_label }}</span>
        <span class="attempt-mark" :class="question.review_overdue ? 'status-overdue' : `status-${question.state}`" :title="`${question.review_overdue ? 'overdue review' : question.state}; ${question.attempt_count} recorded attempts`">{{ question.attempt_count || '' }}</span>
        <b class="row-arrow">→</b>
      </button>
      <div v-if="!loading && !questions?.results.length" class="empty-state">{{ uiText("没有符合当前筛选条件的题目。") }}</div>
    </div>
    <footer v-if="questions && (questions.previous || questions.next)" class="pager"><button :disabled="!questions.previous" @click="page--; loadQuestions()">{{ uiText("← 上一页") }}</button><span>{{ uiText("第") }} {{ page }} {{ uiText("页") }}</span><button :disabled="!questions.next" @click="page++; loadQuestions()">{{ uiText("下一页 →") }}</button></footer>
  </section>
</template>
