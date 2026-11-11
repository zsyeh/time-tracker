<script setup lang="ts">
import { uiText } from '../lib/uiText'
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../lib/api'
import type { InsightPayload } from '../types'
import LearningSharePanel from '../components/LearningSharePanel.vue'
import { useUiPreferences } from '../lib/uiPreferences'

const router = useRouter()
const route = useRoute()
const { language } = useUiPreferences()
const labels = computed(() => language.value === 'zh-CN' ? {
  eyebrow: '作答与笔记', title: '历史记录', description: '按科目、诊断和笔记快速定位需要回看的题目。',
  keyword: '关键词', keywordPlaceholder: '题号、章节或 Note 内容', course: '科目', allCourses: '全部科目',
  book: '书籍', allBooks: '全部书籍', chapter: '章节', allChapters: '全部章节', state: '题目状态',
  allStates: '全部状态', mastered: '已掌握', review: '待复习', diagnosis: '诊断', allDiagnoses: '全部诊断',
  note: '笔记', any: '不限', withNote: '有 Note', withoutNote: '无 Note', start: '开始日期', end: '结束日期',
  sort: '排序', recent: '最近更新', oldest: '最早记录', apply: '应用筛选', clear: '清空',
  loading: '正在加载学习记录…', recentAttempts: '近期作答', questionNotes: '题目笔记 Note',
  noAttempts: '当前筛选下没有作答记录。', noNotes: '当前筛选下没有题目笔记。',
  previous: '上一页', next: '下一页', noDiagnosis: '无结构化诊断', collapse: '收起', expand: '展开全文',
  original: '进入原题 →',
  advanced: '更多筛选', quickFilters: '快速定位',
} : {
  eyebrow: 'Attempts and notes', title: 'History', description: 'Find questions to revisit by subject, diagnosis, and note.',
  keyword: 'Keyword', keywordPlaceholder: 'Question number, chapter, or Note', course: 'Subject', allCourses: 'All subjects',
  book: 'Book', allBooks: 'All books', chapter: 'Chapter', allChapters: 'All chapters', state: 'Question status',
  allStates: 'All statuses', mastered: 'Mastered', review: 'Review', diagnosis: 'Diagnosis', allDiagnoses: 'All diagnoses',
  note: 'Notes', any: 'Any', withNote: 'Has Note', withoutNote: 'No Note', start: 'Start date', end: 'End date',
  sort: 'Sort', recent: 'Recently updated', oldest: 'Oldest first', apply: 'Apply filters', clear: 'Clear',
  loading: 'Loading history…', recentAttempts: 'Recent attempts', questionNotes: 'Question notes',
  noAttempts: 'No attempts match these filters.', noNotes: 'No question notes match these filters.',
  previous: 'Previous', next: 'Next', noDiagnosis: 'No structured diagnosis', collapse: 'Collapse', expand: 'Read full note',
  original: 'Open question →',
  advanced: 'More filters', quickFilters: 'Quick filters',
})
const data = ref<InsightPayload | null>(null)
const loading = ref(true)
const pageLoading = ref(false)
const error = ref('')
const questionsPage = ref(Math.max(1, Number(route.query.questions_page) || 1))
const notesPage = ref(Math.max(1, Number(route.query.notes_page) || 1))
const expandedNotes = ref<Set<string>>(new Set())
const filterKeys = ['q', 'course', 'document', 'topic', 'state', 'error', 'start', 'end', 'has_note', 'sort'] as const
const filters = reactive(Object.fromEntries(filterKeys.map((key) => [
  key, String(route.query[key] || (key === 'sort' ? 'recent' : '')),
])) as Record<typeof filterKeys[number], string>)
const shareScope = computed(() => Object.fromEntries(
  (['q', 'course', 'document', 'topic', 'state', 'error', 'has_note', 'start', 'end'] as const)
    .filter((key) => filters[key]).map((key) => [key, filters[key]]),
))

function activeQuery() {
  return Object.fromEntries([
    ...filterKeys.map((key) => [key, filters[key]] as const),
    ['questions_page', questionsPage.value > 1 ? String(questionsPage.value) : ''],
    ['notes_page', notesPage.value > 1 ? String(notesPage.value) : ''],
  ].filter(([, value]) => value))
}

function openQuestion(uuid: string, list: 'attempts' | 'notes') {
  sessionStorage.setItem('drill.insight.scroll.v1', String(window.scrollY))
  const returnQuery = new URLSearchParams(activeQuery()).toString()
  void router.push({ path: `/practice/${uuid}`, query: { from: 'insight', insight_list: list, insight_return: `/insight${returnQuery ? `?${returnQuery}` : ''}` } })
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat(language.value, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
}

function toggleNote(uuid: string) {
  const next = new Set(expandedNotes.value)
  next.has(uuid) ? next.delete(uuid) : next.add(uuid)
  expandedNotes.value = next
}

async function load(initial = false) {
  if (initial) loading.value = true
  else pageLoading.value = true
  error.value = ''
  try {
    const query = new URLSearchParams(activeQuery()).toString()
    const payload = await api<InsightPayload>(`/api/drill/insight/${query ? `?${query}` : ''}`)
    data.value = payload
    questionsPage.value = payload.recent_questions.page
    notesPage.value = payload.recent_notes.page
    await router.replace({ query: activeQuery() })
  } catch (reason) {
    error.value = (reason as Error).message
  } finally {
    loading.value = false
    pageLoading.value = false
  }
}

async function applyFilters() {
  questionsPage.value = 1
  notesPage.value = 1
  await load()
}

async function resetFilters() {
  filterKeys.forEach((key) => { filters[key] = '' })
  filters.sort = 'recent'
  await applyFilters()
}

async function changePage(kind: 'questions' | 'notes', page: number | null) {
  if (!page || loading.value || pageLoading.value) return
  if (kind === 'questions') questionsPage.value = page
  else notesPage.value = page
  await load()
}

onMounted(async () => {
  await load(true)
  const saved = Number(sessionStorage.getItem('drill.insight.scroll.v1'))
  if (Number.isFinite(saved)) {
    await nextTick()
    window.scrollTo({ top: saved })
    sessionStorage.removeItem('drill.insight.scroll.v1')
  }
})
</script>

<template>
  <section class="page insight-page">
    <header class="page-header"><div><span class="eyebrow">{{ labels.eyebrow }}</span><h1>{{ labels.title }}</h1><p>{{ labels.description }}</p></div></header>
    <LearningSharePanel :current-scope="shareScope" />
    <form class="insight-filters" @submit.prevent="applyFilters">
      <div class="quick-filter-row">
        <label class="keyword-filter">{{ labels.keyword }}<input v-model="filters.q" type="search" :placeholder="labels.keywordPlaceholder"></label>
        <label>{{ labels.state }}<select v-model="filters.state"><option value="">{{ labels.allStates }}</option><option value="mastered">{{ labels.mastered }}</option><option value="review">{{ labels.review }}</option></select></label>
        <div class="filter-actions"><button type="submit">{{ labels.apply }}</button><button type="button" @click="resetFilters">{{ labels.clear }}</button></div>
      </div>
      <details class="advanced-filters" :open="Boolean(filters.course || filters.document || filters.topic || filters.error || filters.has_note || filters.start || filters.end || filters.sort === 'oldest')">
        <summary>{{ labels.advanced }}</summary>
        <div class="advanced-filter-grid">
          <label v-if="data?.options.courses.length">{{ labels.course }}<select v-model="filters.course"><option value="">{{ labels.allCourses }}</option><option v-for="item in data.options.courses" :key="item.code" :value="item.code">{{ item.label }}</option></select></label>
          <label>{{ labels.book }}<select v-model="filters.document"><option value="">{{ labels.allBooks }}</option><option v-for="item in data?.options.documents || []" :key="item.id" :value="item.id">{{ item.label }}</option></select></label>
          <label>{{ labels.chapter }}<select v-model="filters.topic"><option value="">{{ labels.allChapters }}</option><option v-for="item in data?.options.topics || []" :key="item.id" :value="item.id">{{ item.label }}</option></select></label>
          <label>{{ labels.diagnosis }}<select v-model="filters.error"><option value="">{{ labels.allDiagnoses }}</option><option v-for="item in data?.options.errors || []" :key="item.code" :value="item.code">{{ item.code }} · {{ item.label }}</option></select></label>
          <label>{{ labels.note }}<select v-model="filters.has_note"><option value="">{{ labels.any }}</option><option value="1">{{ labels.withNote }}</option><option value="0">{{ labels.withoutNote }}</option></select></label>
          <label>{{ labels.start }}<input v-model="filters.start" type="date"></label>
          <label>{{ labels.end }}<input v-model="filters.end" type="date"></label>
          <label>{{ labels.sort }}<select v-model="filters.sort"><option value="recent">{{ labels.recent }}</option><option value="oldest">{{ labels.oldest }}</option></select></label>
        </div>
      </details>
    </form>
    <p v-if="error" class="error-state">{{ uiText(error) }}</p>
    <div v-else-if="loading" class="question-skeleton">{{ labels.loading }}</div>
    <template v-else-if="data">
      <div class="insight-grid">
        <section class="history-column attempts-column" :class="{ 'is-loading': pageLoading }"><header class="column-heading"><div><span class="eyebrow">{{ labels.recentAttempts }}</span><strong class="column-count">{{ data.recent_questions.count }}</strong></div></header><div class="insight-list"><button v-for="item in data.recent_questions.results" :key="`${item.uuid}-${item.created_at}`" @click="openQuestion(item.uuid, 'attempts')"><span class="history-main"><strong>{{ item.label }}</strong><small>{{ item.document }} · {{ item.topic }}</small><small v-if="item.diagnoses.length" class="diagnosis-line">{{ labels.diagnosis }} · {{ item.diagnoses.join(' / ') }}</small></span><span class="history-meta"><em :class="`text-${item.result === 'review' ? 'review' : 'mastered'}`">{{ item.result === 'review' ? labels.review : labels.mastered }}</em><time>{{ formatTime(item.created_at) }}</time></span></button><p v-if="!data.recent_questions.results.length">{{ labels.noAttempts }}</p></div><footer class="insight-pagination"><button :disabled="!data.recent_questions.previous_page || pageLoading" @click="changePage('questions', data.recent_questions.previous_page)">{{ labels.previous }}</button><span>{{ data.recent_questions.page }} / {{ data.recent_questions.total_pages }}</span><button :disabled="!data.recent_questions.next_page || pageLoading" @click="changePage('questions', data.recent_questions.next_page)">{{ labels.next }}</button></footer></section>
        <section class="history-column notes-column" :class="{ 'is-loading': pageLoading }"><header class="column-heading"><div><span class="eyebrow">{{ labels.questionNotes }}</span><strong class="column-count">{{ data.recent_notes.count }}</strong></div></header><div class="insight-list note-list"><article v-for="item in data.recent_notes.results" :key="item.uuid"><header><button type="button" @click="openQuestion(item.uuid, 'notes')"><strong>{{ item.label }}</strong><small>{{ item.document }} · {{ item.topic }}</small></button><time>{{ formatTime(item.updated_at) }}</time></header><p :class="{ expanded: expandedNotes.has(item.uuid) }">{{ item.note }}</p><footer><span>{{ item.primary_error ? `${labels.diagnosis} · ${item.primary_error}` : labels.noDiagnosis }}</span><button v-if="item.note.length > 90" type="button" @click="toggleNote(item.uuid)">{{ expandedNotes.has(item.uuid) ? labels.collapse : labels.expand }}</button><button type="button" @click="openQuestion(item.uuid, 'notes')">{{ labels.original }}</button></footer></article><p v-if="!data.recent_notes.results.length">{{ labels.noNotes }}</p></div><footer class="insight-pagination"><button :disabled="!data.recent_notes.previous_page || pageLoading" @click="changePage('notes', data.recent_notes.previous_page)">{{ labels.previous }}</button><span>{{ data.recent_notes.page }} / {{ data.recent_notes.total_pages }}</span><button :disabled="!data.recent_notes.next_page || pageLoading" @click="changePage('notes', data.recent_notes.next_page)">{{ labels.next }}</button></footer></section>
      </div>
    </template>
  </section>
</template>

<style scoped>
.insight-page { min-width: 0; }
.insight-page :deep(.page-header) { margin-bottom: 16px; }
.insight-page :deep(.page-header p) { max-width: 60ch; font-size: 14px; line-height: 1.5; }
.insight-filters { display: grid; gap: 8px; margin: 12px 0 16px; padding: 12px; border: 1px solid #242429; border-radius: 12px; background: #151517; }
.quick-filter-row { display: grid; grid-template-columns: minmax(240px, 1fr) minmax(150px, .35fr) auto; align-items: end; gap: 12px; }
.insight-filters label { min-width: 0; display: grid; gap: 6px; color: #a3a3ab; font-size: 12px; }
.insight-filters input, .insight-filters select { width: 100%; min-width: 0; height: 42px; padding: 0 12px; border: 1px solid #303037; border-radius: 8px; color: #e8e8eb; background: #101012; font-size: 14px; }
.filter-actions { display: flex; gap: 8px; }
.filter-actions button { min-height: 42px; padding: 0 16px; border: 1px solid #303037; border-radius: 8px; color: #e8e8eb; background: #1b1b1f; font-size: 14px; cursor: pointer; }
.filter-actions button:first-child { border-color: color-mix(in srgb, var(--accent) 55%, #303037); color: var(--accent); }
.filter-actions button:hover { background: #242429; }
.advanced-filters { border-top: 1px solid #242429; padding-top: 8px; }
.advanced-filters summary { min-height: 36px; display: flex; align-items: center; width: fit-content; color: #a3a3ab; font-size: 13px; cursor: pointer; }
.advanced-filter-grid { padding: 8px 0 2px; display: grid; grid-template-columns: repeat(4, minmax(130px, 1fr)); gap: 12px; }
.insight-grid { min-width: 0; overflow: hidden; display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); border: 1px solid #242429; border-radius: 12px; background: #151517; }
.history-column { min-width: 0; }
.history-column + .history-column { border-left: 1px solid #242429; }
.history-column > .column-heading { height: auto; min-height: 54px; padding: 8px 16px; border-bottom: 1px solid #242429; color: #e8e8eb; font-size: 16px; }
.column-heading > div { width: 100%; display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.column-heading .eyebrow { color: #e8e8eb; font-size: 16px; font-weight: 600; }
.column-count { color: #a3a3ab; font: 600 14px ui-monospace, SFMono-Regular, Menlo, monospace; font-variant-numeric: tabular-nums; }
.insight-list > button { min-height: 76px; padding: 12px 16px; gap: 16px; }
.insight-list > button > .history-main { gap: 5px; }
.insight-list strong { color: #e8e8eb; font-size: 14px; line-height: 1.35; }
.insight-list small, .insight-list time { color: #a3a3ab; font-size: 12px; line-height: 1.4; }
.history-meta { flex: 0 0 auto; display: grid; justify-items: end; gap: 5px; }
.insight-list em { font-size: 12px; font-weight: 600; }
.diagnosis-line { color: #d5a44f !important; }
.insight-list > p { padding: 24px 16px; color: #a3a3ab; font-size: 14px; }
.insight-pagination { min-height: 52px; padding: 8px 12px; }
.insight-pagination button { min-width: 88px; min-height: 40px; padding: 0 12px; font-size: 13px; }
.insight-pagination span { color: #a3a3ab; font-size: 12px; }
.note-list > article { padding: 14px 16px; }
.note-list > article > header button { min-height: 40px; }
.note-list > article > header time { color: #a3a3ab; font-size: 12px; }
.note-list > article > p { max-height: 5.5em; color: #d0d0d5; font-size: 14px; line-height: 1.55; }
.note-list > article > footer { min-height: 34px; gap: 8px; color: #a3a3ab; font-size: 12px; }
.note-list > article > footer button { min-height: 36px; padding: 0 10px; border-radius: 7px; color: #e8e8eb; font-size: 12px; }
.insight-page :deep(.error-state), .insight-page :deep(.question-skeleton) { font-size: 14px; }
@media (max-width: 980px) {
  .insight-grid { grid-template-columns: 1fr 1fr; }
  .quick-filter-row { grid-template-columns: minmax(0, 1fr) minmax(130px, .5fr) auto; }
  .advanced-filter-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 700px) {
  .insight-grid { grid-template-columns: 1fr; }
  .history-column + .history-column { border-top: 1px solid #242429; border-left: 0; }
  .quick-filter-row { grid-template-columns: 1fr 1fr; }
  .keyword-filter { grid-column: 1 / -1; }
  .filter-actions { grid-column: 1 / -1; }
  .filter-actions button { flex: 1; }
}
@media (max-width: 420px) {
  .insight-filters { padding: 10px; }
  .advanced-filter-grid { grid-template-columns: 1fr; }
  .insight-list > button { padding: 11px 12px; gap: 8px; }
  .history-meta { max-width: 120px; text-align: right; }
  .note-list > article { padding: 12px; }
  .note-list > article > header { flex-wrap: wrap; }
}
</style>
