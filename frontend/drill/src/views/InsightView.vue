<script setup lang="ts">
import { uiText } from '../lib/uiText'
import { typeText } from '../lib/examTypes'
import { buildListContext, previewLocation } from '../lib/listContext'
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../lib/api'
import type { InsightPayload } from '../types'
import LearningSharePanel from '../components/LearningSharePanel.vue'
import { useUiPreferences } from '../lib/uiPreferences'
import { runtimeWorkspace } from '../lib/runtimePath'
import { learningUserId } from '../../../shared/foregroundTimer'

const router = useRouter()
const route = useRoute()
const { language } = useUiPreferences()
const labels = computed(() => language.value === 'zh-CN' ? {
  eyebrow: '作答与笔记', title: '历史记录', description: '按科目、诊断和笔记快速定位需要回看的题目。',
  keyword: '关键词', keywordPlaceholder: '题号、章节或 Note 内容', course: '科目', allCourses: '全部科目',
  book: '书籍', allBooks: '全部书籍', chapter: '章节', allChapters: '全部章节', state: '题目状态',
  allStates: '全部状态', mastered: '已掌握', review: '待复习', diagnosis: '诊断', allDiagnoses: '全部诊断',
  note: '笔记', any: '不限', withNote: '有 Note', withoutNote: '无 Note', start: '开始日期', end: '结束日期', dateRange: '日期范围',
  sort: '排序', recent: '最近更新', oldest: '最早记录', apply: '应用筛选', clear: '清空',
  loading: '正在加载学习记录…', recentAttempts: '近期作答', questionNotes: '题目笔记 Note',
  noAttempts: '当前筛选下没有作答记录。', noNotes: '当前筛选下没有题目笔记。',
  previous: '上一页', next: '下一页', noDiagnosis: '无结构化诊断', collapse: '收起', expand: '展开全文',
  original: '进入原题 →', advanced: '高级筛选', filtersActive: '项筛选',
  currentNote: '当前 Note',
} : {
  eyebrow: 'Attempts and notes', title: 'History', description: 'Find questions to revisit by subject, diagnosis, and note.',
  keyword: 'Keyword', keywordPlaceholder: 'Question number, chapter, or Note', course: 'Subject', allCourses: 'All subjects',
  book: 'Book', allBooks: 'All books', chapter: 'Chapter', allChapters: 'All chapters', state: 'Question status',
  allStates: 'All statuses', mastered: 'Mastered', review: 'Review', diagnosis: 'Diagnosis', allDiagnoses: 'All diagnoses',
  note: 'Notes', any: 'Any', withNote: 'Has Note', withoutNote: 'No Note', start: 'Start date', end: 'End date', dateRange: 'Date range',
  sort: 'Sort', recent: 'Recently updated', oldest: 'Oldest first', apply: 'Apply filters', clear: 'Clear',
  loading: 'Loading history…', recentAttempts: 'Recent attempts', questionNotes: 'Question notes',
  noAttempts: 'No attempts match these filters.', noNotes: 'No question notes match these filters.',
  previous: 'Previous', next: 'Next', noDiagnosis: 'No structured diagnosis', collapse: 'Collapse', expand: 'Read full note',
  original: 'Open question →', advanced: 'More filters', filtersActive: 'filters active',
  currentNote: 'Current Note',
})
const data = ref<InsightPayload | null>(null)
const loading = ref(true)
const pageLoading = ref(false)
const error = ref('')
const questionsPage = ref(Math.max(1, Number(route.query.questions_page) || 1))
const notesPage = ref(Math.max(1, Number(route.query.notes_page) || 1))
const filterKeys = ['q', 'course', 'document', 'topic', 'state', 'error', 'start', 'end', 'has_note', 'sort'] as const
const advancedKeys = ['course', 'document', 'topic', 'error', 'has_note'] as const
const filters = reactive(Object.fromEntries(filterKeys.map((key) => [
  key, String(route.query[key] || (key === 'sort' ? 'recent' : '')),
])) as Record<typeof filterKeys[number], string>)
const appliedFilters = reactive({ ...filters })
const advancedOpen = ref(advancedKeys.some((key) => Boolean(route.query[key])))
const advancedCount = computed(() => advancedKeys.filter((key) => filters[key]).length)
const mobileDatesOpen = ref(Boolean(filters.start || filters.end))
const dateSummary = computed(() => [filters.start, filters.end].filter(Boolean).join(' – '))
const storagePrefix = `${runtimeWorkspace}.insight.v2.${learningUserId || 'anonymous'}`
function readState(kind: 'scroll' | 'list' | 'expanded') {
  try {
    return sessionStorage.getItem(`${storagePrefix}.${kind}`)
      // Only an unscoped fixture/anonymous session can consume an old unscoped cache.
      || (!learningUserId && runtimeWorkspace === 'drill' ? sessionStorage.getItem(`drill.insight.${kind}.v1`) : null)
  } catch { return null }
}
function writeState(kind: string, value: string) {
  try { sessionStorage.setItem(`${storagePrefix}.${kind}`, value) } catch { /* Optional browser state. */ }
}
const activeList = ref<'attempts' | 'notes'>(readState('list') === 'notes' ? 'notes' : 'attempts')
const expandedNotes = ref<Set<string>>(new Set())
try {
  const expanded = JSON.parse(readState('expanded') || '[]')
  if (Array.isArray(expanded)) expandedNotes.value = new Set(expanded.filter(item => typeof item === 'string').slice(-100))
} catch { /* Malformed local state does not block history. */ }
const shareScope = computed(() => Object.fromEntries(
  (['q', 'course', 'document', 'topic', 'state', 'error', 'has_note', 'start', 'end'] as const)
    .filter((key) => appliedFilters[key]).map((key) => [key, appliedFilters[key]]),
))
let sequence = 0
let request: AbortController | null = null
let searchTimer = 0
let composing = false
let hydratingFilters = false
let replacingQuery = false
let alive = true
let restoreCancelled = false

function activeQuery() {
  return Object.fromEntries([
    ...filterKeys.map((key) => [key, appliedFilters[key]] as const),
    ['questions_page', questionsPage.value > 1 ? String(questionsPage.value) : ''],
    ['notes_page', notesPage.value > 1 ? String(notesPage.value) : ''],
  ].filter(([, value]) => value))
}
function querySignature() { return new URLSearchParams(activeQuery()).toString() }
function openQuestion(uuid: string, list: 'attempts' | 'notes') {
  writeState('scroll', JSON.stringify({ top: window.scrollY, query: querySignature() }))
  writeState('list', list)
  const returnQuery = new URLSearchParams(Object.fromEntries(Object.entries(route.query).filter((entry): entry is [string, string] => typeof entry[1] === 'string'))).toString()
  void router.push({ path: `/practice/${uuid}`, query: { from: 'insight', insight_list: list, insight_return: `/insight${returnQuery ? `?${returnQuery}` : ''}` } })
}
function previewList(list: 'attempts' | 'notes') {
  writeState('scroll', JSON.stringify({ top: window.scrollY, query: querySignature() }))
  writeState('list', list)
  const query = Object.fromEntries(filterKeys.filter(key => appliedFilters[key]).map(key => [key, appliedFilters[key]]))
  const first = list === 'attempts' ? data.value?.recent_questions.results[0] : data.value?.recent_notes.results[0]
  const entry = list === 'attempts' && first && 'attempt_id' in first ? `attempt:${first.attempt_id}` : undefined
  void router.push(previewLocation(buildListContext(list, query, route.fullPath), entry, first?.uuid))
}
function selectList(list: 'attempts' | 'notes') {
  activeList.value = list
  writeState('list', list)
}
function navigateTab(event: KeyboardEvent) {
  if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
  event.preventDefault()
  selectList(event.key === 'Home' ? 'attempts' : event.key === 'End' ? 'notes' : activeList.value === 'attempts' ? 'notes' : 'attempts')
  document.getElementById(`insight-${activeList.value}-tab`)?.focus()
}
function formatTime(value: string) {
  return new Intl.DateTimeFormat(language.value, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
}
function toggleNote(uuid: string) {
  const next = new Set(expandedNotes.value)
  next.has(uuid) ? next.delete(uuid) : next.add(uuid)
  expandedNotes.value = new Set([...next].slice(-100))
  writeState('expanded', JSON.stringify([...expandedNotes.value]))
}
async function load(initial = false) {
  const current = ++sequence
  request?.abort()
  const controller = new AbortController(); request = controller
  if (initial) loading.value = true
  else pageLoading.value = true
  error.value = ''
  try {
    const query = new URLSearchParams(activeQuery()).toString()
    const payload = await api<InsightPayload>(`/api/drill/insight/${query ? `?${query}` : ''}`, { signal: controller.signal })
    if (!alive || current !== sequence) return false
    data.value = payload
    questionsPage.value = payload.recent_questions.page
    notesPage.value = payload.recent_notes.page
    replacingQuery = true
    try { await router.replace({ query: activeQuery() }) } finally { replacingQuery = false }
    return alive && current === sequence
  } catch (reason) {
    if (alive && current === sequence && !controller.signal.aborted) error.value = (reason as Error).message
    return false
  } finally {
    if (alive && current === sequence) { loading.value = false; pageLoading.value = false }
  }
}
async function applyFilters() {
  if (composing) return
  window.clearTimeout(searchTimer)
  Object.assign(appliedFilters, filters)
  questionsPage.value = 1; notesPage.value = 1
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
function scheduleSearch() {
  window.clearTimeout(searchTimer)
  if (hydratingFilters || composing) return
  // Supersede an old response as soon as text changes, including the debounce window.
  sequence += 1; request?.abort()
  searchTimer = window.setTimeout(() => {
    appliedFilters.q = filters.q
    questionsPage.value = 1; notesPage.value = 1
    void load()
  }, 250)
}
function compositionStarted() {
  composing = true; sequence += 1; request?.abort(); window.clearTimeout(searchTimer)
}
function compositionEnded(event: CompositionEvent) {
  composing = false
  filters.q = (event.target as HTMLInputElement).value
  scheduleSearch()
}
watch(() => filters.q, scheduleSearch, { flush: 'sync' })
watch(() => JSON.stringify(route.query), () => {
  if (replacingQuery) return
  const next = Object.fromEntries(filterKeys.map(key => [key, String(route.query[key] || (key === 'sort' ? 'recent' : ''))]))
  const questionPage = Math.max(1, Number(route.query.questions_page) || 1)
  const notePage = Math.max(1, Number(route.query.notes_page) || 1)
  if (filterKeys.every(key => next[key] === appliedFilters[key]) && questionPage === questionsPage.value && notePage === notesPage.value) return
  window.clearTimeout(searchTimer); hydratingFilters = true
  Object.assign(filters, next); Object.assign(appliedFilters, next)
  hydratingFilters = false
  questionsPage.value = questionPage; notesPage.value = notePage
  void load()
})
function cancelRestore() { restoreCancelled = true }
onMounted(async () => {
  window.addEventListener('wheel', cancelRestore, { passive: true })
  window.addEventListener('touchstart', cancelRestore, { passive: true })
  window.addEventListener('pointerdown', cancelRestore, { passive: true })
  window.addEventListener('keydown', cancelRestore)
  if (!await load(true)) return
  const storedScroll = readState('scroll')
  if (storedScroll === null) return
  try {
    const saved = JSON.parse(storedScroll)
    const top = typeof saved === 'number' ? saved : saved.top
    if (!Number.isFinite(top) || (typeof saved === 'object' && saved.query !== querySignature())) return
    await nextTick()
    if (document.fonts?.status === 'loading') await Promise.race([document.fonts.ready, new Promise(resolve => window.setTimeout(resolve, 200))])
    if (typeof window.requestAnimationFrame === 'function') await new Promise<void>(resolve => window.requestAnimationFrame(() => window.requestAnimationFrame(() => resolve())))
    if (!alive || restoreCancelled) return
    window.scrollTo({ top: Math.max(0, top) })
    try {
      sessionStorage.removeItem(`${storagePrefix}.scroll`)
      if (!learningUserId) sessionStorage.removeItem('drill.insight.scroll.v1')
    } catch { /* Optional cache. */ }
  } catch { /* Invalid cached scroll is ignored. */ }
})
onUnmounted(() => {
  alive = false; sequence += 1; request?.abort(); window.clearTimeout(searchTimer)
  window.removeEventListener('wheel', cancelRestore)
  window.removeEventListener('touchstart', cancelRestore)
  window.removeEventListener('pointerdown', cancelRestore)
  window.removeEventListener('keydown', cancelRestore)
})
</script>

<template>
  <section class="page insight-page">
    <header class="page-header"><div><h1>{{ labels.title }}</h1><p>{{ labels.description }}</p></div></header>
    <form class="insight-filters" @submit.prevent="applyFilters">
      <div class="filter-primary">
        <label class="wide">{{ labels.keyword }}<input v-model="filters.q" type="search" :placeholder="labels.keywordPlaceholder" @compositionstart="compositionStarted" @compositionend="compositionEnded"></label>
        <label>{{ labels.state }}<select v-model="filters.state"><option value="">{{ labels.allStates }}</option><option value="mastered">{{ labels.mastered }}</option><option value="review">{{ labels.review }}</option></select></label>
        <label class="filter-sort">{{ labels.sort }}<select v-model="filters.sort"><option value="recent">{{ labels.recent }}</option><option value="oldest">{{ labels.oldest }}</option></select></label>
        <details class="filter-dates-mobile" :open="mobileDatesOpen" @toggle="mobileDatesOpen = ($event.target as HTMLDetailsElement).open">
          <summary>{{ labels.dateRange }}<span v-if="dateSummary">{{ dateSummary }}</span></summary>
          <div class="filter-dates-fields">
            <label>{{ labels.start }}<input v-model="filters.start" type="date"></label>
            <label>{{ labels.end }}<input v-model="filters.end" type="date"></label>
          </div>
        </details>
        <button class="filter-submit" type="submit">{{ labels.apply }}</button>
        <button class="filter-more" type="button" :aria-expanded="advancedOpen" aria-controls="insight-advanced-filters" @click="advancedOpen = !advancedOpen">{{ labels.advanced }}<span v-if="advancedCount" class="filter-count">{{ advancedCount }}</span></button>
      </div>
      <div v-if="advancedOpen" id="insight-advanced-filters" class="filter-advanced">
        <label v-if="data?.options.courses.length">{{ labels.course }}<select v-model="filters.course"><option value="">{{ labels.allCourses }}</option><option v-for="item in data.options.courses" :key="item.code" :value="item.code">{{ item.label }}</option></select></label>
        <label>{{ labels.book }}<select v-model="filters.document"><option value="">{{ labels.allBooks }}</option><option v-for="item in data?.options.documents || []" :key="item.id" :value="item.id">{{ item.label }}</option></select></label>
        <label>{{ labels.chapter }}<select v-model="filters.topic"><option value="">{{ labels.allChapters }}</option><option v-for="item in data?.options.topics || []" :key="item.id" :value="item.id">{{ item.label }}</option></select></label>
        <label>{{ labels.diagnosis }}<select v-model="filters.error"><option value="">{{ labels.allDiagnoses }}</option><option v-for="item in data?.options.errors || []" :key="item.code" :value="item.code">{{ item.code }} · {{ item.label }}</option></select></label>
        <label>{{ labels.note }}<select v-model="filters.has_note"><option value="">{{ labels.any }}</option><option value="1">{{ labels.withNote }}</option><option value="0">{{ labels.withoutNote }}</option></select></label>
        <button class="filter-clear" type="button" @click="resetFilters">{{ labels.clear }}</button>
      </div>
    </form>
    <p v-if="error" class="error-state">{{ uiText(error) }}</p>
    <div v-else-if="loading" class="question-skeleton">{{ labels.loading }}</div>
    <template v-else-if="data">
      <div class="insight-tabs" role="tablist" :aria-label="labels.title" @keydown="navigateTab">
        <button id="insight-attempts-tab" type="button" role="tab" :aria-selected="activeList === 'attempts'" :tabindex="activeList === 'attempts' ? 0 : -1" aria-controls="insight-attempts" @click="selectList('attempts')">{{ labels.recentAttempts }} <span>{{ data.recent_questions.count }}</span></button>
        <button id="insight-notes-tab" type="button" role="tab" :aria-selected="activeList === 'notes'" :tabindex="activeList === 'notes' ? 0 : -1" aria-controls="insight-notes" @click="selectList('notes')">{{ labels.questionNotes }} <span>{{ data.recent_notes.count }}</span></button>
      </div>
      <div class="insight-grid">
        <section id="insight-attempts" :class="{ 'is-loading': pageLoading, 'mobile-hidden': activeList !== 'attempts' }" :aria-busy="pageLoading" role="tabpanel" aria-labelledby="insight-attempts-tab"><header><span>{{ labels.recentAttempts }}</span><strong>{{ data.recent_questions.count }}</strong><button type="button" data-preview-list="attempts" :disabled="pageLoading || !data.recent_questions.count" @click="previewList('attempts')">{{ typeText('全局预览', 'Preview all') }}</button></header><div class="insight-list"><button v-for="item in data.recent_questions.results" :key="item.attempt_id" type="button" @click="openQuestion(item.uuid, 'attempts')"><span class="record-main"><strong>{{ item.label }}</strong><small>{{ item.document }} · {{ item.topic }}</small><small v-if="item.diagnoses.length" class="record-diagnosis">{{ labels.diagnosis }} {{ item.diagnoses.join(' / ') }}</small><small v-if="item.note_excerpt" class="record-note">{{ labels.currentNote }} · {{ item.note_excerpt }}</small></span><span class="record-meta"><em :class="`text-${item.result === 'review' ? 'review' : 'mastered'}`">{{ item.result === 'review' ? labels.review : labels.mastered }}</em><time :datetime="item.created_at">{{ formatTime(item.created_at) }}</time></span></button><p v-if="!data.recent_questions.results.length">{{ labels.noAttempts }}</p></div><footer class="insight-pagination"><button type="button" :disabled="!data.recent_questions.previous_page || pageLoading" @click="changePage('questions', data.recent_questions.previous_page)">{{ labels.previous }}</button><span>{{ data.recent_questions.page }} / {{ data.recent_questions.total_pages }}</span><button type="button" :disabled="!data.recent_questions.next_page || pageLoading" @click="changePage('questions', data.recent_questions.next_page)">{{ labels.next }}</button></footer></section>
        <section id="insight-notes" :class="{ 'is-loading': pageLoading, 'mobile-hidden': activeList !== 'notes' }" :aria-busy="pageLoading" role="tabpanel" aria-labelledby="insight-notes-tab"><header><span>{{ labels.questionNotes }}</span><strong>{{ data.recent_notes.count }}</strong><button type="button" data-preview-list="notes" :disabled="pageLoading || !data.recent_notes.count" @click="previewList('notes')">{{ typeText('全局预览', 'Preview all') }}</button></header><div class="insight-list note-list"><article v-for="item in data.recent_notes.results" :key="item.uuid"><header><button type="button" @click="openQuestion(item.uuid, 'notes')"><strong>{{ item.label }}</strong><small>{{ item.document }} · {{ item.topic }}</small></button><time :datetime="item.updated_at">{{ formatTime(item.updated_at) }}</time></header><p :id="`note-body-${item.uuid}`" :class="{ expanded: expandedNotes.has(item.uuid) }">{{ item.note }}</p><footer><span>{{ item.primary_error ? `${labels.diagnosis} ${item.primary_error}` : labels.noDiagnosis }}</span><button v-if="item.note.length > 90" type="button" :aria-expanded="expandedNotes.has(item.uuid)" :aria-controls="`note-body-${item.uuid}`" @click="toggleNote(item.uuid)">{{ expandedNotes.has(item.uuid) ? labels.collapse : labels.expand }}</button><button type="button" @click="openQuestion(item.uuid, 'notes')">{{ labels.original }}</button></footer></article><p v-if="!data.recent_notes.results.length">{{ labels.noNotes }}</p></div><footer class="insight-pagination"><button type="button" :disabled="!data.recent_notes.previous_page || pageLoading" @click="changePage('notes', data.recent_notes.previous_page)">{{ labels.previous }}</button><span>{{ data.recent_notes.page }} / {{ data.recent_notes.total_pages }}</span><button type="button" :disabled="!data.recent_notes.next_page || pageLoading" @click="changePage('notes', data.recent_notes.next_page)">{{ labels.next }}</button></footer></section>
      </div>
    </template>
    <LearningSharePanel :current-scope="shareScope" />
  </section>
</template>

<style scoped>
[data-preview-list] { min-height:44px; margin-left:auto; padding:8px 12px; font-size:13px; }

.insight-page { container-type: inline-size; color: var(--text-primary); }
.insight-filters { display: block; margin: 0 0 24px; padding: 0; background: transparent; border: 0; }
.filter-primary { display: grid; grid-template-columns: minmax(160px, 1fr) minmax(120px, 148px) minmax(120px, 148px) auto auto; align-items: end; gap: 8px; }
.filter-dates-mobile { display: block; order: 1; grid-column: 1 / -1; min-width: 0; }
.filter-dates-mobile summary { display:flex; align-items:center; gap:8px; min-height:44px; color:var(--text-secondary); font-size:13px; cursor:pointer; list-style:none; }
.filter-dates-mobile summary::-webkit-details-marker { display:none; }
.filter-dates-mobile summary::before { content:""; width:6px; height:6px; flex:none; border-right:1.5px solid currentColor; border-bottom:1.5px solid currentColor; transform:rotate(-45deg); }
.filter-dates-mobile[open] summary::before { transform:rotate(45deg); }
.filter-dates-mobile summary span { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.filter-dates-fields { display:grid; grid-template-columns:repeat(2,minmax(0,140px)); gap:8px; }
.insight-filters label { display: grid; gap: 4px; min-width: 0; color: var(--text-secondary); font-size: 12px; line-height: 1.35; }
.insight-filters input, .insight-filters select { box-sizing: border-box; max-width:100%; width: 100%; min-width: 0; min-height: 44px; padding: 4px 8px; border: 1px solid var(--border-control); border-radius: var(--radius-sm); color: var(--text-primary); background: var(--bg-elevated); font: inherit; font-size: 14px; }
.insight-filters button { white-space: nowrap; min-height: 44px; padding: 0 12px; font: inherit; font-size: 13px; font-weight: 600; cursor: pointer; }
.insight-filters input:focus-visible, .insight-filters select:focus-visible, .insight-filters button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.filter-submit { border: 0; border-radius: var(--radius-sm); color: var(--accent-on-solid); background: var(--accent-solid); }
.filter-more, .filter-clear { border: 0; border-radius: var(--radius-sm); color: var(--text-secondary); background: transparent; }
.filter-more:hover, .filter-clear:hover { color: var(--text-primary); background: var(--bg-surface-hover); }
.filter-count { display: inline-grid; place-items: center; min-width: 18px; height: 18px; margin-left: 6px; border-radius: 9px; color: var(--text-primary); background: var(--surface-selected); font-size: 12px; }
.filter-advanced { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); align-items: end; gap: 12px; margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--border-subtle); }
.filter-clear { justify-self: start; }
.insight-tabs { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); margin-bottom: 8px; border-bottom: 1px solid var(--border-subtle); }
.insight-tabs button { min-height: 44px; padding: 8px; border: 0; border-bottom: 2px solid transparent; color: var(--text-secondary); background: transparent; font: inherit; font-size: 14px; font-weight: 600; cursor: pointer; }
.insight-tabs button[aria-selected="true"] { border-bottom-color: var(--text-primary); color: var(--text-primary); }
.insight-tabs span { margin-left: 4px; color: var(--text-secondary); font-size: 12px; font-variant-numeric: tabular-nums; }
.insight-grid { display: grid; grid-template-columns: minmax(0, 1fr); min-width: 0; background: transparent; }
.insight-grid > section { display: flex; flex-direction: column; min-width: 0; border: 0; }
.insight-grid > section:first-child { border-left: 0; }
.insight-grid > section.is-loading { cursor: progress; }
.insight-grid > section.mobile-hidden { display: none; }
.insight-grid > section > header { display: flex; align-items: center; justify-content: space-between; min-height: 48px; padding: 12px 16px; border-bottom: 1px solid var(--border-subtle); color: var(--text-primary); font-size: 17px; font-weight: 600; }
.insight-grid > section > header strong { color: var(--text-secondary); font-size: 13px; font-variant-numeric: tabular-nums; }
.insight-list { flex: 1; }
.insight-list > button { display: flex; align-items: center; justify-content: space-between; width: 100%; min-height: 72px; padding: 12px 16px; gap: 12px; border: 0; border-bottom: 1px solid var(--border-subtle); color: var(--text-primary); background: transparent; text-align: left; cursor: pointer; }
.insight-list > button:hover { background: var(--bg-surface-hover); }
.insight-list > button:focus-visible, .note-list button:focus-visible, .insight-tabs button:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }
.insight-list > button > .record-main { flex: 1; display: grid; min-width: 0; gap: 4px; }
.insight-list > button > .record-meta { display: grid; flex: none; align-items: end; gap: 6px; text-align: right; }
.insight-list strong { display: block; overflow: hidden; color: var(--text-primary); font-size: 14px; font-weight: 600; line-height: 1.35; text-overflow: ellipsis; white-space: nowrap; }
.insight-list small, .insight-list time { color: var(--text-secondary); font-size: 12px; line-height: 1.35; font-variant-numeric: tabular-nums; }
.record-main > small { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.insight-list .record-diagnosis { color: var(--text-secondary); }
.insight-list .record-note { overflow: hidden; color: var(--text-secondary); display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; white-space: normal; }
.insight-list em { justify-self: end; padding: 0; background: transparent; font-size: 12px; font-style: normal; font-weight: 600; }
.insight-list > p { margin: 0; padding: 24px 16px; color: var(--text-secondary); font-size: 14px; }
.insight-pagination { display: flex; align-items: center; justify-content: space-between; gap: 8px; min-height: 54px; padding: 8px 16px; border-top: 1px solid var(--border-subtle); }
.insight-pagination button { min-height: 44px; padding: 0 12px; border: 0; border-radius: var(--radius-sm); color: var(--text-secondary); background: transparent; font: inherit; font-size: 13px; cursor: pointer; }
.insight-pagination button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.insight-pagination button:hover:not(:disabled) { color: var(--text-primary); background: var(--bg-surface-hover); }
.insight-pagination button:disabled { opacity: .4; cursor: default; }
.insight-pagination span { color: var(--text-secondary); font-size: 12px; font-variant-numeric: tabular-nums; }
.note-list > article { padding: 12px 16px; border-bottom: 1px solid var(--border-subtle); }
.note-list > article > header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.note-list > article > header button { display: grid; min-width: 0; min-height: 44px; gap: 4px; padding: 0; border: 0; color: var(--text-primary); background: transparent; text-align: left; cursor: pointer; }
.note-list > article > header button:hover strong { color: var(--accent); }
.note-list > article > header time { flex: none; color: var(--text-secondary); text-align: right; }
.note-list > article > p { overflow: hidden; max-height: 3em; margin: 8px 0; color: var(--text-primary); font-size: 14px; line-height: 1.5; white-space: pre-wrap; }
.note-list > article > p.expanded { max-height: none; }
.note-list > article > footer { display: flex; align-items: center; flex-wrap: wrap; justify-content: flex-start; gap: 8px; color: var(--text-secondary); font-size: 12px; }
.note-list > article > footer span { margin-right: auto; }
.note-list > article > footer button { min-height: 44px; padding: 4px 12px; border: 0; border-radius: var(--radius-sm); color: var(--text-secondary); background: transparent; font: inherit; font-size: 13px; cursor: pointer; }
.note-list > article > footer button:hover { color: var(--text-primary); border-color: var(--border-strong); }
@container (min-width: 900px) {
  .insight-grid { grid-template-columns: minmax(0, 3fr) minmax(0, 2fr); gap: 24px; }
  .insight-grid > section.mobile-hidden { display: flex; }
  .insight-tabs { display: none; }
  .insight-grid > section + section { border-left: 1px solid var(--border-subtle); padding-left: 8px; }
}
@container (max-width: 760px) {
  .filter-primary { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto; gap: 8px; }
  .filter-primary .wide { grid-column: 1 / -1; }
  .filter-primary > label:not(.wide):not(.filter-sort) { grid-column: 1; grid-row: 2; }
  .filter-sort { grid-column: 2; grid-row: 2; }
  .filter-submit { grid-column: 3; grid-row: 2; }
  .filter-more { grid-column: 3; grid-row: 3; align-self: start; }
  .insight-filters input, .insight-filters select { font-size: 16px; }
  .filter-dates { display: none; }
  .filter-dates-mobile { display: block; grid-column: 1 / 3; grid-row: 3; min-width: 0; }
  .filter-dates-mobile summary { display: flex; align-items: center; gap: 8px; min-height: 44px; padding: 8px 0; border: 0; color: var(--text-secondary); background: transparent; font-size: 13px; font-weight: 500; list-style: none; cursor: pointer; }
  .filter-dates-mobile summary::-webkit-details-marker { display: none; }
  .filter-dates-mobile summary::before { content: ''; width: 6px; height: 6px; flex: none; border-right: 1.5px solid currentColor; border-bottom: 1.5px solid currentColor; transform: rotate(-45deg); }
  .filter-dates-mobile[open] summary::before { transform: rotate(45deg); }
  .filter-dates-mobile summary:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
  .filter-dates-mobile summary span { overflow: hidden; color: var(--text-primary); font-variant-numeric: tabular-nums; font-weight: 400; text-overflow: ellipsis; white-space: nowrap; }
  .filter-dates-fields { display: grid; grid-template-columns: minmax(0, 1fr); gap: 8px; padding-top: 4px; }
  .filter-advanced { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .insight-list > button { padding: 12px 0; }
  .insight-grid > section > header { padding-inline: 0; }
  .note-list > article { padding-inline: 0; }
  .record-meta { max-width: 96px; }
}
@container (max-width: 420px) {
  .filter-primary { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }
  .filter-primary .wide { grid-column: 1 / -1; }
  .filter-primary > label:not(.wide):not(.filter-sort) { grid-column: 1; grid-row: 2; }
  .filter-sort { grid-column: 2; grid-row: 2; }
  .filter-dates-mobile { grid-column: 1; grid-row: 3; }
  .filter-more { grid-column: 2; grid-row: 3; }
  .filter-submit { grid-column: 1 / -1; grid-row: 4; }
  .filter-advanced { grid-template-columns: minmax(0, 1fr); }
  .record-meta { max-width: 88px; }
  .note-list > article > header { align-items: start; flex-direction: column; gap: 4px; }
}
@media (pointer: coarse) { .insight-filters input, .insight-filters select { font-size: 16px; } }
</style>
