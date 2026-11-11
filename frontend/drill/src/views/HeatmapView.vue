<script setup lang="ts">
import { uiText } from '../lib/uiText'
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../lib/api'
import { cachedHeatmap, storeHeatmap } from '../lib/workspace'
import { useUiPreferences } from '../lib/uiPreferences'
import ExamTypeControls from '../components/ExamTypeControls.vue'
import ExamTypeBadge from '../components/ExamTypeBadge.vue'
import { formatColours, type TypeStats } from '../lib/examTypes'
import HeatmapProgress from '../components/HeatmapProgress.vue'
import LearningSharePanel from '../components/LearningSharePanel.vue'

const props = withDefaults(defineProps<{ selectedOnly?: boolean; coreOnly?: boolean }>(), { selectedOnly: false, coreOnly: false })
const { t } = useUiPreferences()

interface HeatmapQuestion {
  question_type?: string
  type_group?: string
  course?: string
  core_topic?: string
  source_indexed?: boolean
  uuid: string
  order: number
  label: string
  topic: string
  year: number | null
  variant: string
  attempt_count: number
  latest_result: string | null
  review_overdue: boolean
  state: 'unattempted' | 'mastered' | 'review'
}

interface HeatmapTopic {
  topic_id: number
  topic: string
  path: string
  question_count: number
  attempted_question_count: number
  mastered_question_count: number
  review_question_count: number
  attempt_count: number
  coverage_percent: number
  intensity: 0 | 1 | 2 | 3 | 4
  state: 'unattempted' | 'progress' | 'mastered' | 'review' | 'overdue'
}

interface HeatmapPayload {
  type_statistics?: TypeStats
  curation_total?: number
  quality_notice?: string
  courses?: { key: string; title: string; total: number; visible: number }[]
  question_count: number
  topic_count: number
  statistics: {
    attempted_question_count: number
    mastered_question_count: number
    review_question_count: number
    master_rate_percent: number | null
    timed_attempt_count: number
    average_time_seconds: number | null
    mastered_average_time_seconds: number | null
    review_average_time_seconds: number | null
  }
  groups: Array<{
    document_id: number
    document: string
    questions: HeatmapQuestion[]
    topics: HeatmapTopic[]
    statistics: {
      attempted_question_count: number
      mastered_question_count: number
      review_question_count: number
      coverage_percent: number
      master_rate_percent: number | null
      timed_attempt_count: number
      average_time_seconds: number | null
      mastered_average_time_seconds: number | null
      review_average_time_seconds: number | null
    }
  }>
}

function formatDuration(seconds: number | null) {
  if (seconds === null) return '—'
  const minutes = Math.floor(seconds / 60)
  const remainder = seconds % 60
  if (minutes >= 60) return `${Math.floor(minutes / 60)}h ${minutes % 60}m`
  return minutes ? `${minutes}m ${remainder}s` : `${remainder}s`
}

const router = useRouter()
const route = useRoute()
const typeGroup = ref(String(route.query.type_group || ''))
const course = ref(String(route.query.course || ''))
const material = ref(String(route.query.material || 'ready'))
const data = ref<HeatmapPayload | null>(null)
const loading = ref(true)
const error = ref('')
const initialScope = ['past_exam', 'mock_exam', 'all'].includes(String(route.query.scope))
  ? String(route.query.scope) as 'past_exam' | 'mock_exam' | 'all'
  : 'all'
const initialMode = ['topics', 'questions'].includes(String(route.query.mode))
  ? String(route.query.mode) as 'topics' | 'questions'
  : 'questions'
const scope = ref<'past_exam' | 'mock_exam' | 'all'>(initialScope)
const shareScope = computed(() => ({
  source_category: scope.value, type_group: typeGroup.value,
  ...(props.coreOnly ? { collection: 'core_selected', course: course.value, material: material.value }
    : props.selectedOnly ? { collection: 'selected' } : {}),
}))
const mode = ref<'topics' | 'questions'>(props.selectedOnly ? 'questions' : initialMode)
let pendingQuestionUuid = String(route.query.question || '')
const returnStateKey = 'drill.heatmap.return.v1'
const selectedTopic = ref<{
  documentId: number
  document: string
  topic: HeatmapTopic
} | null>(null)
const selectedQuestion = ref<{
  documentId: number
  document: string
  question: HeatmapQuestion
} | null>(null)
let loadSequence = 0

function previewTopic(documentId: number, document: string, topic: HeatmapTopic) {
  selectedQuestion.value = null
  selectedTopic.value = { documentId, document, topic }
}

function previewQuestion(documentId: number, document: string, question: HeatmapQuestion) {
  if (question.source_indexed) {
    openQuestion(documentId, question)
    return
  }
  selectedTopic.value = null
  selectedQuestion.value = { documentId, document, question }
}

function openTopic(documentId: number, topicId: number) {
  void router.push({
    path: '/practice',
    query: { document: String(documentId), topic: String(topicId), type_group: typeGroup.value, ...(props.selectedOnly ? { collection: 'selected' } : {}) },
  })
}

function openQuestion(documentId: number, question: HeatmapQuestion) {
  if (props.coreOnly) {
    void router.push({ path: `/practice/${question.uuid}`, query: {
      type_group: typeGroup.value, collection: 'core_selected', from: 'core-heatmap', scope: scope.value,
      course: course.value, material: material.value,
    } })
    return
  }
  sessionStorage.setItem(returnStateKey, JSON.stringify({
    scope: scope.value,
    questionUuid: question.uuid,
    scrollY: window.scrollY,
  }))
  const query: Record<string, string> = {
    type_group: typeGroup.value, ...(props.selectedOnly ? { collection: 'selected' } : {}),
    document: String(documentId),
    from: props.selectedOnly ? 'selected-heatmap' : 'heatmap',
    heat_scope: scope.value,
    heat_question: question.uuid,
  }
  if (scope.value !== 'all') query.source_category = scope.value
  void router.push({ path: `/practice/${question.uuid}`, query })
}

async function restoreQuestionSelection(payload: HeatmapPayload) {
  if (mode.value !== 'questions' || !pendingQuestionUuid) return
  for (const group of payload.groups) {
    const question = group.questions.find((item) => item.uuid === pendingQuestionUuid)
    if (!question) continue
    selectedQuestion.value = { documentId: group.document_id, document: group.document, question }
    await nextTick()
    let restoredScroll = false
    try {
      const saved = JSON.parse(sessionStorage.getItem(returnStateKey) || 'null')
      if (saved?.scope === scope.value && saved?.questionUuid === question.uuid) {
        window.scrollTo({ top: Number(saved.scrollY) || 0, behavior: 'auto' })
        restoredScroll = true
      }
    } catch {
      // A malformed browser cache must not block heatmap navigation.
    }
    if (!restoredScroll) {
      document.querySelector(`[data-question-uuid="${question.uuid}"]`)?.scrollIntoView({ block: 'center' })
    }
    pendingQuestionUuid = ''
    return
  }
}

function smallPractice() {
  void router.push({ path: '/practice', query: {
    type_group: 'small', ...(scope.value !== 'all' ? { source_category: scope.value } : {}),
    ...(props.coreOnly ? { collection: 'core_selected', course: course.value, material: material.value } : props.selectedOnly ? { collection: 'selected' } : {}),
  } })
}

async function load() {
  const sequence = ++loadSequence
  const requestedScope = scope.value
  const requestedMode = mode.value
  const requestedSelectedOnly = props.selectedOnly
  const requestedCoreOnly = props.coreOnly
  const collection = props.coreOnly ? 'core_selected' : requestedSelectedOnly ? 'selected' : ''
  const extra = `&type_group=${encodeURIComponent(typeGroup.value)}` + (props.coreOnly ? `&course=${encodeURIComponent(course.value)}&material=${encodeURIComponent(material.value)}` : '')
  const cacheKey = `${collection || 'all'}:${requestedMode}:${requestedScope}:${extra}`
  const cached = cachedHeatmap<HeatmapPayload>(cacheKey)
  if (cached) {
    data.value = cached
    void restoreQuestionSelection(cached)
  }
  loading.value = !cached
  error.value = ''
  try {
    const value = await api<HeatmapPayload>(`/api/drill/heatmap/?scope=${requestedScope}&mode=${requestedMode}${collection ? `&collection=${collection}` : ''}${extra}`)
    if (sequence !== loadSequence || scope.value !== requestedScope || mode.value !== requestedMode || props.selectedOnly !== requestedSelectedOnly || props.coreOnly !== requestedCoreOnly) return
    data.value = value
    storeHeatmap(cacheKey, value)
    void restoreQuestionSelection(value)
  } catch (reason) {
    error.value = (reason as Error).message
  } finally {
    if (sequence === loadSequence && scope.value === requestedScope && mode.value === requestedMode && props.selectedOnly === requestedSelectedOnly) loading.value = false
  }
}

watch([scope, mode, course, material], () => {
  selectedTopic.value = null
  selectedQuestion.value = null
  pendingQuestionUuid = ''
  void load()
})
watch(() => [props.selectedOnly, props.coreOnly], () => {
  const selectedOnly = props.selectedOnly
  scope.value = ['past_exam','mock_exam','all'].includes(String(route.query.scope)) ? String(route.query.scope) as 'all' | 'past_exam' | 'mock_exam' : 'all'
  course.value = String(route.query.course || '')
  material.value = String(route.query.material || 'ready')
  // Vue Router reuses this component between /heatmap and
  // /selected-heatmap. Reset route-specific state before loading the other
  // collection so stale requests and previews cannot bleed across pages.
  data.value = null
  selectedTopic.value = null
  selectedQuestion.value = null
  pendingQuestionUuid = String(route.query.question || '')
  if (selectedOnly && mode.value !== 'questions') {
    mode.value = 'questions'
    return
  }
  void load()
})
watch(typeGroup, () => { selectedTopic.value = null; selectedQuestion.value = null; void load() })
onMounted(load)
</script>

<template>
  <section :class="{ 'exam-type-colours': formatColours, 'selected-heatmap-page': props.selectedOnly }" class="page heatmap-page">
    <header class="page-header">
      <div><span class="eyebrow">{{ props.coreOnly ? 'CORE COLLECTION' : props.selectedOnly ? t('selectedHeatmap') : t('knowledgeMap') }}</span><h1>{{ props.coreOnly ? uiText("五科核心题热力图") : props.selectedOnly ? t('selectedHeatmap') : t('coverageByBook') }}</h1><p>{{ props.coreOnly ? 'Browse five core subjects by source book and topic.' : props.selectedOnly ? 'Curated questions grouped by source book and topic.' : 'Choose a question or topic to preview it and start practicing.' }}</p></div>
      <div class="heat-controls">
        <div v-if="!props.selectedOnly" class="heat-mode"><button :class="{ active: mode === 'topics' }" @click="mode = 'topics'">Topics</button><button :class="{ active: mode === 'questions' }" @click="mode = 'questions'">Questions</button></div>
        <div class="heat-scope"><button :class="{ active: scope === 'all' }" @click="scope = 'all'">{{ uiText("All") }}</button><button :class="{ active: scope === 'past_exam' }" @click="scope = 'past_exam'">Past exams</button><button :class="{ active: scope === 'mock_exam' }" @click="scope = 'mock_exam'">Mock exams</button></div>
        <div class="heat-legend" aria-label="Question status legend"><span><i class="status-unattempted" />Not started</span><span><i class="status-progress" />In progress</span><span><i class="status-mastered" />Mastered</span><span><i class="status-review" />Review</span><span><i class="status-overdue" />Overdue</span></div>
      </div>
    </header>
    <ExamTypeControls v-model="typeGroup" :stats="data?.type_statistics" @practice="smallPractice" />
    <div v-if="props.coreOnly" class="core-controls">
      <label>{{ uiText("学科") }}<select v-model="course"><option value="">{{ uiText("全部五科") }}</option><option v-for="item in data?.courses || []" :key="item.key" :value="item.key">{{ item.title }} {{ uiText("· 核心") }} {{ item.total }} {{ uiText("题") }}</option></select></label>
      <label>{{ uiText("资料") }}<select v-model="material"><option value="ready">{{ uiText("题答已具备，且无未处理勘误") }}</option><option value="all">{{ uiText("全部核心（含待补资料）") }}</option></select></label>
      <p>{{ data?.quality_notice }} <template v-if="data?.curation_total">{{ uiText("核心清单共") }} {{ data.curation_total }} {{ uiText("题，当前显示") }} {{ data.question_count }} {{ uiText("题。") }}</template></p>
    </div>
    <p v-if="error" class="error-state">{{ uiText(error) }}</p>
    <div v-else-if="loading" class="question-skeleton">BUILDING HEATMAP…</div>
    <template v-else-if="data">
      <HeatmapProgress :total="data.question_count" :attempted="data.statistics.attempted_question_count" :mastered="data.statistics.mastered_question_count" />
      <details class="heatmap-summary">
        <summary><strong>{{ uiText('平均用时统计') }}</strong><span>{{ formatDuration(data.statistics.average_time_seconds) }} · {{ data.statistics.timed_attempt_count }} timed</span></summary>
        <dl>
          <div><dt>AVG. TIME</dt><dd>{{ formatDuration(data.statistics.average_time_seconds) }}</dd><small>{{ data.statistics.timed_attempt_count }} timed attempts</small></div>
          <div><dt>MASTER AVG.</dt><dd>{{ formatDuration(data.statistics.mastered_average_time_seconds) }}</dd><small>Mastered submissions</small></div>
          <div><dt>REVIEW AVG.</dt><dd>{{ formatDuration(data.statistics.review_average_time_seconds) }}</dd><small>{{ data.statistics.review_question_count }} currently in review</small></div>
        </dl>
      </details>
      <section v-for="group in data.groups" :key="group.document_id" class="heatmap-group">
        <header class="heatmap-book-header">
          <div class="heatmap-book-title"><span>BOOK</span><h2>{{ group.document }}</h2><small>{{ mode === 'topics' ? `${group.topics.length} topics` : `${group.questions.length} questions` }}</small></div>
          <dl class="heatmap-book-stats">
            <div><dt>COVERAGE</dt><dd>{{ group.statistics.coverage_percent }}%</dd><small>{{ group.statistics.attempted_question_count }} attempted</small></div>
            <div><dt>AVG. TIME</dt><dd>{{ formatDuration(group.statistics.average_time_seconds) }}</dd><small>{{ group.statistics.timed_attempt_count }} timed</small></div>
            <div><dt>MASTER AVG.</dt><dd>{{ formatDuration(group.statistics.mastered_average_time_seconds) }}</dd><small>{{ group.statistics.review_question_count }} review</small></div>
          </dl>
        </header>
        <div class="heatmap-book-progress" role="progressbar" :aria-label="`${group.document} question coverage`" :aria-valuemin="0" :aria-valuemax="100" :aria-valuenow="group.statistics.coverage_percent"><i :style="{ width: `${group.statistics.coverage_percent}%` }" /></div>
        <div v-if="mode === 'topics'" class="topic-heatmap">
          <button
            v-for="item in group.topics"
            :key="item.topic_id"
            :class="[`status-${item.state}`, `intensity-${item.intensity}`, { selected: selectedTopic?.topic.topic_id === item.topic_id }]"
            :aria-pressed="selectedTopic?.topic.topic_id === item.topic_id"
            :aria-label="`${item.path}; ${item.coverage_percent}% covered; ${item.attempt_count} attempts`"
            :title="`${item.path} · ${item.attempted_question_count}/${item.question_count} covered · ${item.attempt_count} attempts${item.review_question_count ? ` · ${item.review_question_count} review` : ''}`"
            @click="previewTopic(group.document_id, group.document, item)"
          ><span>{{ item.topic }}</span></button>
        </div>
        <Transition name="topic-preview">
          <aside v-if="mode === 'topics' && selectedTopic?.documentId === group.document_id" class="topic-preview-card">
            <div class="topic-preview-copy">
              <span>TOPIC PREVIEW · {{ selectedTopic.document }}</span>
              <h3>{{ selectedTopic.topic.topic }}</h3>
              <p>{{ selectedTopic.topic.path }}</p>
            </div>
            <dl>
              <div><dt>COVERED</dt><dd>{{ selectedTopic.topic.attempted_question_count }} / {{ selectedTopic.topic.question_count }}</dd></div>
              <div><dt>ATTEMPTS</dt><dd>{{ selectedTopic.topic.attempt_count }}</dd></div>
              <div><dt>REVIEW</dt><dd>{{ selectedTopic.topic.review_question_count }}</dd></div>
            </dl>
            <div class="topic-preview-actions">
              <button type="button" class="topic-preview-close" @click="selectedTopic = null">Close</button>
              <button type="button" class="topic-preview-open" @click="openTopic(selectedTopic.documentId, selectedTopic.topic.topic_id)">Practice this topic <b>→</b></button>
            </div>
          </aside>
        </Transition>
        <div v-if="mode === 'questions'" class="question-heatmap">
          <button
            v-for="(item, index) in group.questions"
            :key="item.uuid"
            :data-question-uuid="item.uuid" :data-type-group="item.type_group"
            :class="[item.review_overdue ? 'status-overdue' : `status-${item.state}`, { selected: selectedQuestion?.question.uuid === item.uuid }]"
            :aria-pressed="selectedQuestion?.question.uuid === item.uuid"
            :aria-label="`${item.label}; ${item.state}; ${item.attempt_count} attempts`"
            :title="`${item.label} · ${item.core_topic || item.topic} · ${item.state} · ${item.attempt_count} attempts`"
            @click="previewQuestion(group.document_id, group.document, item)"
          ><span class="exam-heat-dot" :class="`exam-dot-${item.type_group || 'unknown'}`" /><span>{{ props.coreOnly ? index + 1 : item.year }}</span></button>
        </div>
        <Transition name="topic-preview">
          <aside v-if="mode === 'questions' && selectedQuestion?.documentId === group.document_id" class="topic-preview-card question-preview-card">
            <div class="topic-preview-copy">
              <span>QUESTION PREVIEW · {{ selectedQuestion.document }}</span>
              <ExamTypeBadge :type="selectedQuestion.question.question_type" :group="selectedQuestion.question.type_group" /><h3>{{ selectedQuestion.question.label || `Question ${selectedQuestion.question.order}` }}</h3>
              <p>{{ selectedQuestion.question.core_topic || selectedQuestion.question.topic || uiText("General") }}<template v-if="selectedQuestion.question.year"> · {{ selectedQuestion.question.year }}{{ selectedQuestion.question.variant ? ` ${selectedQuestion.question.variant}` : '' }}</template></p>
            </div>
            <dl>
              <div><dt>STATE</dt><dd>{{ selectedQuestion.question.review_overdue ? 'OVERDUE REVIEW' : selectedQuestion.question.state === 'mastered' ? 'MASTERED' : selectedQuestion.question.state === 'review' ? 'REVIEW' : 'NOT STARTED' }}</dd></div>
              <div><dt>ATTEMPTS</dt><dd>{{ selectedQuestion.question.attempt_count }}</dd></div>
              <div><dt>INDEX</dt><dd>{{ String(selectedQuestion.question.order).padStart(4, '0') }}</dd></div>
            </dl>
            <div class="topic-preview-actions">
              <button type="button" class="topic-preview-close" @click="selectedQuestion = null">Close</button>
              <button type="button" class="topic-preview-open" @click="openQuestion(selectedQuestion.documentId, selectedQuestion.question)">Open question <b>→</b></button>
            </div>
          </aside>
        </Transition>
      </section>
      <LearningSharePanel :current-scope="shareScope" />
    </template>
  </section>
</template>

<style scoped>
.heatmap-page { min-width: 0; }
.heatmap-page > .page-header { align-items: flex-start; gap: 24px; }
.heatmap-page > .page-header > div:first-child { min-width: 0; }
.heatmap-page > .page-header h1 { font-size: clamp(24px, 2.4vw, 28px); letter-spacing: -.025em; line-height: 1.18; }
.heatmap-page > .page-header p { max-width: 60ch; margin-top: 8px; color: var(--text-secondary); font-size: 14px; line-height: 1.5; }

.heat-controls { min-width: max-content; gap: 8px; }
.heat-mode, .heat-scope { gap: 2px; padding: 3px; border-color: var(--border-default); border-radius: 9px; background: var(--bg-surface); }
.heat-mode button, .heat-scope button { min-height: 36px; padding: 0 12px; border-radius: 6px; color: var(--text-secondary); font-size: 13px; font-weight: 550; touch-action: manipulation; }
.heat-mode button.active, .heat-scope button.active { color: var(--text-primary); background: var(--bg-elevated); box-shadow: inset 0 0 0 1px var(--border-default); }
.heat-mode button:focus-visible, .heat-scope button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.heat-legend { display: flex; align-items: center; justify-content: flex-end; flex-wrap: wrap; gap: 6px 12px; color: var(--text-secondary); font-size: 12px; }
.heat-legend > span { display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; }
.heat-legend i { width: 12px; height: 12px; border: 1px solid var(--border-default); border-radius: 3px; display: inline-block; }

.core-controls { display: flex; flex-wrap: wrap; gap: 12px; margin: 16px 0 20px; padding: 16px; border: 1px solid var(--border-subtle); border-radius: var(--radius-md); background: var(--bg-surface); }
.core-controls label { display: grid; gap: 6px; min-width: 180px; max-width: 100%; color: var(--text-secondary); font-size: 13px; }
.core-controls select { min-width: 0; max-width: 100%; min-height: 42px; padding: 8px 12px; color: var(--text-primary); background: var(--bg-app); border: 1px solid var(--border-default); border-radius: var(--radius-sm); font-size: 14px; }
.core-controls p { flex-basis: 100%; margin: 0; color: var(--text-secondary); font-size: 13px; line-height: 1.6; }

.heatmap-page :deep(.heatmap-progress) { margin-bottom: 16px; overflow: hidden; border-color: var(--border-default); border-radius: 10px; background: var(--bg-surface); }
.heatmap-page :deep(.heatmap-progress > div) { padding: 12px 14px; border-color: var(--border-subtle); }
.heatmap-page :deep(.heatmap-progress dt) { font-size: 12px; letter-spacing: 0; }
.heatmap-page :deep(.heatmap-progress dd) { margin-top: 6px; font-size: 22px; }
.heatmap-page :deep(.heatmap-progress small) { font-size: 12px; line-height: 1.35; }
.heatmap-page :deep(.heatmap-progress [data-progress="mastered"] dd) { color: var(--success, #55b88a); }
.heatmap-page :deep(.heatmap-progress [data-progress="unattempted"] dd) { color: var(--text-secondary); }
.selected-heatmap-page :deep(.exam-type-stats) { gap: 8px; margin-top: 8px; }
.selected-heatmap-page :deep(.exam-type-stats button) { gap: 4px; padding: 8px 10px; }
.selected-heatmap-page :deep(.exam-type-stats strong) { font-size: 14px; }
.selected-heatmap-page :deep(.exam-type-stats span) { font-size: 12px; line-height: 1.35; }

.heatmap-summary { margin: 0 0 16px; overflow: hidden; border: 1px solid var(--border-subtle); border-radius: 10px; background: var(--bg-surface); }
.heatmap-summary > summary { min-height: 42px; padding: 8px 14px; color: var(--text-secondary); display: flex; align-items: center; justify-content: space-between; gap: 12px; list-style: none; cursor: pointer; }
.heatmap-summary > summary::-webkit-details-marker { display: none; }
.heatmap-summary > summary::after { content: '+'; color: var(--text-tertiary); font-size: 16px; }
.heatmap-summary[open] > summary { border-bottom: 1px solid var(--border-subtle); }
.heatmap-summary[open] > summary::after { content: '−'; }
.heatmap-summary > summary strong { color: var(--text-primary); font-size: 13px; font-weight: 600; }
.heatmap-summary > summary span { margin-left: auto; color: var(--text-tertiary); font-size: 12px; font-variant-numeric: tabular-nums; }
.heatmap-summary dl { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.heatmap-summary dl > div { padding: 12px 16px; border-color: var(--border-subtle); }
.heatmap-summary dt { color: var(--text-secondary); font-size: 12px; letter-spacing: .035em; }
.heatmap-summary dd { margin: 6px 0 2px; font-size: 16px; }
.heatmap-summary small { color: var(--text-tertiary); font-size: 12px; }

.heatmap-group { margin-top: 20px; padding: 16px; border-color: var(--border-subtle); border-radius: 12px; background: var(--bg-surface); min-width: 0; }
.heatmap-group > header { margin-bottom: 14px; gap: 16px; }
.heatmap-book-title { min-width: 180px; }
.heatmap-group > header span { font-size: 12px; letter-spacing: .04em; }
.heatmap-group h2 { margin-top: 4px; font-size: 17px; font-weight: 620; line-height: 1.35; overflow-wrap: anywhere; }
.heatmap-book-title small { margin-top: 5px; font-size: 12px; }
.heatmap-book-stats { grid-template-columns: repeat(3, minmax(90px, auto)); }
.heatmap-book-stats > div { padding: 4px 14px; border-color: var(--border-subtle); }
.heatmap-book-stats dt { color: var(--text-secondary); font-size: 12px; letter-spacing: .025em; }
.heatmap-book-stats dd { margin-top: 5px; font-size: 15px; }
.heatmap-book-stats small { display: block; margin-top: 3px; color: var(--text-tertiary); font-size: 12px; }
.heatmap-book-progress { height: 4px; margin: 2px 0 16px; overflow: hidden; border-radius: 4px; background: var(--border-subtle); }
.heatmap-book-progress i { display: block; height: 100%; border-radius: inherit; background: var(--success); }

.topic-heatmap { display: grid; grid-template-columns: repeat(auto-fill, 26px); gap: 5px; }
.topic-heatmap button, .question-heatmap button { width: 26px; height: 26px; border-radius: 5px; touch-action: manipulation; transition: transform 100ms ease, border-color 100ms ease; }
.topic-heatmap button span, .question-heatmap button span { display: none; }
.topic-heatmap button:hover, .question-heatmap button:hover { border-color: var(--text-secondary); transform: scale(1.08); z-index: 1; }
.topic-heatmap button.selected, .question-heatmap button.selected { outline: 2px solid var(--accent); outline-offset: 2px; z-index: 2; }
.topic-heatmap button:focus-visible, .question-heatmap button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; z-index: 3; }
.question-heatmap { grid-template-columns: repeat(auto-fill, 24px); gap: 5px; }
.question-heatmap button { width: 24px; height: 24px; }
.exam-heat-dot { top: 3px; right: 3px; width: 6px; height: 6px; }
.exam-dot-small { background: var(--accent); }.exam-dot-large { background: var(--warning); }.exam-dot-short_answer { background: #a895da; }

.topic-preview-card { margin-top: 16px; padding: 16px; border-color: var(--border-default); border-radius: 10px; background: var(--bg-elevated); gap: 16px; }
.topic-preview-copy > span { color: var(--text-secondary); font-size: 12px; letter-spacing: .035em; }
.topic-preview-copy h3 { margin: 6px 0 4px; font-size: 16px; line-height: 1.35; }
.topic-preview-copy p { color: var(--text-secondary); font-size: 13px; line-height: 1.45; }
.topic-preview-card dl { gap: 18px; }
.topic-preview-card dt { color: var(--text-secondary); font-size: 12px; }
.topic-preview-card dd { margin-top: 4px; font-size: 14px; font-variant-numeric: tabular-nums; }
.topic-preview-actions { gap: 8px; }
.topic-preview-actions button { min-height: 42px; padding: 0 14px; border-radius: 7px; font-size: 13px; font-weight: 550; touch-action: manipulation; }

@media (max-width: 900px) {
  .heatmap-page > .page-header { align-items: flex-start; }
  .heatmap-page > .page-header .heat-controls { min-width: 0; }
  .heatmap-group > header { align-items: flex-start !important; flex-direction: row; flex-wrap: wrap; }
  .heatmap-book-title { flex: 1 1 200px; }
  .heatmap-book-stats { width: auto; flex: 1 1 100%; }
  .heatmap-book-stats > div:first-child { border-left: 0; padding-left: 0; }
}
@media (max-width: 700px) {
  .heatmap-page > .page-header { gap: 12px; }
  .heatmap-page > .page-header .heat-controls { width: 100%; justify-items: stretch; }
  .heat-mode, .heat-scope { max-width: 100%; }
  .heat-mode button, .heat-scope button { flex: 1; padding-inline: 8px; }
  .heat-legend { justify-content: flex-start; gap: 8px 12px; }
  .core-controls { padding: 12px; }
  .core-controls label { min-width: 100%; }
  .heatmap-page :deep(.heatmap-progress) { grid-template-columns: repeat(6, minmax(0, 1fr)); }
  .heatmap-page :deep(.heatmap-progress > div) { grid-column: span 2; padding: 10px; }
  .heatmap-page :deep(.heatmap-progress > div:nth-child(n+4)) { grid-column: span 3; border-top: 1px solid var(--border-subtle); }
  .heatmap-page :deep(.heatmap-progress > div:nth-child(4)) { border-left: 0; }
  .selected-heatmap-page :deep(.heatmap-progress) { grid-template-columns: repeat(5, minmax(0, 1fr)); }
  .selected-heatmap-page :deep(.heatmap-progress > div) { grid-column: auto !important; padding: 8px 5px; border-top: 0 !important; }
  .selected-heatmap-page :deep(.heatmap-progress > div + div) { border-left: 1px solid var(--border-subtle) !important; }
  .selected-heatmap-page :deep(.heatmap-progress dt) { font-size: 11px; line-height: 1.25; }
  .selected-heatmap-page :deep(.heatmap-progress dd) { margin-top: 4px; font-size: 18px; }
  .selected-heatmap-page :deep(.heatmap-progress small) { font-size: 10px; }
  .heatmap-summary dl { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .heatmap-summary dl > div { padding: 11px 12px; }
  .heatmap-summary dl > div:nth-child(3) { grid-column: 1/-1; border-top: 1px solid var(--border-subtle); border-left: 0; }
  .heatmap-book-stats { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .heatmap-book-stats > div { padding: 8px; }
  .heatmap-book-stats > div:first-child { padding-left: 0; }
  .heatmap-book-stats > div:nth-child(3) { border-top: 0; border-left: 1px solid var(--border-subtle); padding-left: 8px; }
  .topic-heatmap { grid-template-columns: repeat(auto-fill, 28px); gap: 6px; }
  .topic-heatmap button { width: 28px; height: 28px; }
  .question-heatmap { grid-template-columns: repeat(auto-fill, 26px); gap: 5px; }
  .question-heatmap button { width: 26px; height: 26px; }
  .topic-preview-card { grid-template-columns: 1fr; gap: 12px; }
  .topic-preview-card dl { justify-content: flex-start; flex-wrap: wrap; gap: 12px 22px; }
  .topic-preview-actions { grid-column: auto; }
  .topic-preview-actions button { flex: 1; }
}
</style>
