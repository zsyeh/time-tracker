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
const returnStateKey = computed(() => `drill.heatmap.return.v2.${props.coreOnly ? 'core' : props.selectedOnly ? 'selected' : 'all'}`)
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
  try {
    sessionStorage.setItem(returnStateKey.value, JSON.stringify({
      scope: scope.value, typeGroup: typeGroup.value, course: course.value,
      material: material.value, questionUuid: question.uuid, scrollY: window.scrollY,
    }))
  } catch {
    // Private browsing may disallow storage; the return route still selects the question.
  }
  if (props.coreOnly) {
    void router.push({ path: `/practice/${question.uuid}`, query: {
      type_group: typeGroup.value, collection: 'core_selected', from: 'core-heatmap', scope: scope.value,
      course: course.value, material: material.value,
    } })
    return
  }
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
      const saved = JSON.parse(sessionStorage.getItem(returnStateKey.value) || 'null')
      if (saved?.scope === scope.value && saved?.typeGroup === typeGroup.value
        && saved?.course === course.value && saved?.material === material.value
        && saved?.questionUuid === question.uuid) {
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
  <section :class="{ 'exam-type-colours': formatColours }" class="page heatmap-page">
    <header class="page-header">
      <div><h1>{{ props.coreOnly ? uiText("五科核心题热力图") : props.selectedOnly ? t('selectedHeatmap') : t('coverageByBook') }}</h1><p>{{ uiText('按题册浏览，选择题目继续练习。') }}</p></div>
      <div class="heat-controls">
        <div v-if="!props.selectedOnly" class="heat-mode"><button :class="{ active: mode === 'topics' }" @click="mode = 'topics'">Topics</button><button :class="{ active: mode === 'questions' }" @click="mode = 'questions'">Questions</button></div>
        <div class="heat-scope"><button :class="{ active: scope === 'all' }" @click="scope = 'all'">{{ uiText("All") }}</button><button :class="{ active: scope === 'past_exam' }" @click="scope = 'past_exam'">Past exams</button><button :class="{ active: scope === 'mock_exam' }" @click="scope = 'mock_exam'">Mock exams</button></div>
        <div class="heat-legend" aria-label="题目状态图例"><i class="status-unattempted" /><span>未做</span><i class="status-progress" /><span>进行中</span><i class="status-mastered" /><span>已掌握</span><i class="status-review" /><span>待复习</span><i class="status-overdue" /><span>已到期</span></div>
      </div>
    </header>
    <ExamTypeControls v-model="typeGroup" @practice="smallPractice" />
    <div v-if="props.coreOnly" class="core-controls">
      <label>{{ uiText("学科") }}<select v-model="course"><option value="">{{ uiText("全部五科") }}</option><option v-for="item in data?.courses || []" :key="item.key" :value="item.key">{{ item.title }} {{ uiText("· 核心") }} {{ item.total }} {{ uiText("题") }}</option></select></label>
      <label>{{ uiText("资料") }}<select v-model="material"><option value="ready">{{ uiText("题答已具备，且无未处理勘误") }}</option><option value="all">{{ uiText("全部核心（含待补资料）") }}</option></select></label>
      <p>{{ data?.quality_notice }} <template v-if="data?.curation_total">{{ uiText("核心清单共") }} {{ data.curation_total }} {{ uiText("题，当前显示") }} {{ data.question_count }} {{ uiText("题。") }}</template></p>
    </div>
    <p v-if="error" class="error-state">{{ uiText(error) }}</p>
    <div v-else-if="loading" class="question-skeleton">BUILDING HEATMAP…</div>
    <template v-else-if="data">
      <div class="heatmap-overview" aria-label="当前范围进度"><strong>{{ data.question_count }}</strong><span>题</span><span>已做 <b>{{ data.statistics.attempted_question_count }}</b></span><span>已掌握 <b>{{ data.statistics.mastered_question_count }}</b></span><span>待复习 <b>{{ data.statistics.review_question_count }}</b></span></div>
      <section v-for="group in data.groups" :key="group.document_id" class="heatmap-group">
        <header class="heatmap-book-header">
          <div class="heatmap-book-title"><h2>{{ group.document }}</h2><small>{{ mode === 'topics' ? `${group.topics.length} 个考点` : `${group.questions.length} 题` }}</small></div>
          <div class="heatmap-book-stats"><strong>{{ group.statistics.coverage_percent }}%</strong><span>已做 {{ group.statistics.attempted_question_count }} · 已掌握 {{ group.statistics.mastered_question_count }} · 待复习 {{ group.statistics.review_question_count }}</span></div>
        </header>
        <div v-if="mode === 'topics'" class="topic-heatmap">
          <button
            v-for="item in group.topics"
            :key="item.topic_id"
            :class="[`status-${item.state}`, `intensity-${item.intensity}`, { selected: selectedTopic?.topic.topic_id === item.topic_id }]"
            :aria-pressed="selectedTopic?.topic.topic_id === item.topic_id"
            :aria-label="`${item.path}; ${item.state}; ${item.coverage_percent}% covered; ${item.attempt_count} attempts`"
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
.heatmap-page { font-variant-numeric: tabular-nums; }
.heatmap-page .page-header { margin-bottom: 8px; align-items: flex-start; }
.heatmap-page .page-header h1 { margin: 0; font-size: 24px; line-height: 1.25; font-weight: 650; }
.heatmap-page .page-header p { margin: 4px 0 0; color: var(--text-secondary); font-size: 13px; }
.heat-controls { display: flex; flex-wrap: wrap; justify-content: flex-end; align-items: center; gap: 8px; }
.heat-mode, .heat-scope { padding: 3px; border: 1px solid var(--border-subtle); border-radius: 8px; background: var(--bg-surface); }
.heat-mode button, .heat-scope button { min-height: 36px; padding: 0 12px; border-radius: 6px; font-size: 12px; }
.heat-mode button.active, .heat-scope button.active { color: var(--text-primary); background: var(--bg-elevated); }
.heat-legend { gap: 5px; font-size: 12px; }
.heat-legend i:not(:first-child) { margin-left: 8px; }
.heatmap-page :deep(.exam-type-controls) { margin: 8px 0 16px; }
.heatmap-page :deep(.exam-type-toolbar small) { display: none; }
.heatmap-page :deep(.exam-type-toolbar select), .heatmap-page :deep(.exam-small-entry) { min-height: 40px; }
.heatmap-overview { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 12px; margin: 0 0 8px; color: var(--text-secondary); font-size: 13px; }
.heatmap-overview strong { color: var(--text-primary); font-size: 24px; font-weight: 650; line-height: 1; }
.heatmap-overview span:nth-of-type(n+2) { margin-left: 8px; }
.heatmap-overview b { color: var(--text-primary); font-weight: 600; }
.heatmap-group { margin-top: 8px; padding: 16px; border: 1px solid var(--border-subtle); border-radius: 10px; background: var(--bg-surface); }
.heatmap-group > header { margin-bottom: 12px; gap: 12px; }
.heatmap-group h2 { margin: 0; font-size: 17px; line-height: 1.35; font-weight: 650; }
.heatmap-book-title { min-width: 0; }
.heatmap-book-title small { margin-top: 4px; color: var(--text-secondary); font-size: 12px; }
.heatmap-book-stats { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 12px; color: var(--text-secondary); font-size: 12px; }
.heatmap-book-stats strong { color: var(--text-primary); font-size: 16px; }
.topic-heatmap { grid-template-columns: repeat(auto-fill, 26px); gap: 5px; }
.question-heatmap { grid-template-columns: repeat(auto-fill, 24px); gap: 5px; }
.topic-heatmap button, .question-heatmap button { width: 26px; height: 26px; border-radius: 4px; touch-action: manipulation; }
.question-heatmap button { width: 24px; height: 24px; }
.topic-heatmap button.selected, .question-heatmap button.selected { outline: 2px solid var(--accent); outline-offset: 2px; z-index: 1; }
.topic-heatmap button:focus-visible, .question-heatmap button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.topic-preview-card { padding: 16px; background: var(--bg-elevated); gap: 16px; }
.topic-preview-copy > span, .topic-preview-card dt { font-size: 12px; }
.topic-preview-copy h3 { font-size: 16px; }
.topic-preview-copy p { color: var(--text-secondary); font-size: 13px; }
.topic-preview-card dd { color: var(--text-primary); font-size: 14px; font-variant-numeric: tabular-nums; }
.topic-preview-actions button { min-height: 40px; padding: 0 12px; font-size: 13px; }
.core-controls { margin: 8px 0 16px; }
.core-controls label { font-size: 13px; color: var(--text-secondary); }
.core-controls select { min-height: 40px; }
.core-controls p { margin: 0; font-size: 12px; }
.question-heatmap button { position:relative; }
.exam-heat-dot { position:absolute; top:2px; right:2px; width:5px; height:5px; border-radius:50%; background:var(--text-secondary); }
.exam-dot-small { background:var(--accent); }.exam-dot-large { background:var(--warning); }.exam-dot-short_answer { background:#a895da; }

.core-controls { display:flex; flex-wrap:wrap; gap:12px; margin:16px 0; }
.core-controls label { display:grid; gap:6px; min-width:0; max-width:100%; font-size:12px; }
.core-controls select { min-width:0; max-width:100%; padding:10px; color:var(--text-primary); background:var(--bg-surface); border:1px solid var(--border-default); border-radius:var(--radius-sm); }
.core-controls p { flex-basis:100%; color:var(--text-secondary); line-height:1.7; }
@media (max-width: 900px) {
  .heatmap-group > header { align-items: flex-start; }
  .heatmap-book-stats { width: auto; }
}
@media (max-width: 700px) {
  .heat-controls { justify-content: flex-start; }
  .heat-legend { display: flex; flex-wrap: wrap; }
  .heatmap-group { padding: 12px; }
  .heatmap-book-stats { display: flex; }
  .topic-preview-card { grid-template-columns: 1fr; }
  .heatmap-page .page-header { padding-left: 52px; }
}
</style>
