<script setup lang="ts">
import { uiText } from '../lib/uiText'
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
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
type QuickState = 'all' | 'unattempted' | 'review' | 'mastered' | 'overdue'
const quickState = ref<QuickState>('all')
const hasOverdue = computed(() => data.value?.groups.some(group => group.questions.some(question => question.review_overdue)) ?? false)
const locateMessage = ref('')
let locateTimer = 0
try {
  const saved = JSON.parse(sessionStorage.getItem(returnStateKey.value) || 'null')
  if (pendingQuestionUuid && saved?.questionUuid === pendingQuestionUuid && ['all', 'unattempted', 'review', 'mastered', 'overdue'].includes(saved.quickState)) quickState.value = saved.quickState
} catch { /* Return state is optional. */ }
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
      material: material.value, quickState: quickState.value, questionUuid: question.uuid, scrollY: window.scrollY,
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
  const restoringUuid = pendingQuestionUuid
  const restoringSequence = loadSequence
  for (const group of payload.groups) {
    const question = group.questions.find((item) => item.uuid === restoringUuid)
    if (!question) continue
    selectedQuestion.value = { documentId: group.document_id, document: group.document, question }
    await nextTick()
    if (typeof window.requestAnimationFrame === 'function') {
      await new Promise<void>((resolve) => window.requestAnimationFrame(() => resolve()))
    }
    if (restoringSequence !== loadSequence || pendingQuestionUuid !== restoringUuid || String(route.query.question || '') !== restoringUuid) return
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

function matchesQuickState(question: HeatmapQuestion) {
  if (quickState.value === 'all') return true
  if (quickState.value === 'overdue') return question.review_overdue
  return question.state === quickState.value
}

function locateNextUnattempted() {
  const ordered = data.value?.groups.flatMap(group => group.questions.map(question => ({ group, question }))) || []
  const currentIndex = ordered.findIndex(({ question }) => question.uuid === selectedQuestion.value?.question.uuid)
  const afterCurrent = ordered.slice(currentIndex + 1).find(({ question }) => question.state === 'unattempted' && matchesQuickState(question))
  const target = afterCurrent || ordered.find(({ question }) => question.state === 'unattempted' && matchesQuickState(question))
  window.clearTimeout(locateTimer)
  if (!target) {
    locateMessage.value = uiText('当前筛选范围没有未做题')
    locateTimer = window.setTimeout(() => { locateMessage.value = '' }, 3000)
    return
  }
  selectedTopic.value = null
  selectedQuestion.value = { documentId: target.group.document_id, document: target.group.document, question: target.question }
  void nextTick(() => {
    document.querySelector(`[data-question-uuid="${target.question.uuid}"]`)?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  })
  locateMessage.value = uiText('已定位下一道未做题')
  locateTimer = window.setTimeout(() => { locateMessage.value = '' }, 3000)
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
  }
  loading.value = !cached
  error.value = ''
  try {
    const value = await api<HeatmapPayload>(`/api/drill/heatmap/?scope=${requestedScope}&mode=${requestedMode}${collection ? `&collection=${collection}` : ''}${extra}`)
    if (sequence !== loadSequence || scope.value !== requestedScope || mode.value !== requestedMode || props.selectedOnly !== requestedSelectedOnly || props.coreOnly !== requestedCoreOnly) return
    data.value = value
    storeHeatmap(cacheKey, value)
  } catch (reason) {
    error.value = (reason as Error).message
  } finally {
    if (sequence === loadSequence && scope.value === requestedScope && mode.value === requestedMode && props.selectedOnly === requestedSelectedOnly) {
      loading.value = false
      if (data.value) void restoreQuestionSelection(data.value)
    }
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
onUnmounted(() => { loadSequence += 1; window.clearTimeout(locateTimer) })
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
    <div v-else-if="loading" class="question-skeleton">{{ uiText('正在加载热力图…') }}</div>
    <template v-else-if="data">
      <div class="heatmap-overview" aria-label="当前范围进度"><strong>{{ data.question_count }}</strong><span>{{ uiText('题') }}</span><span>{{ uiText('已做') }} <b>{{ data.statistics.attempted_question_count }}</b></span><span>{{ uiText('已掌握') }} <b>{{ data.statistics.mastered_question_count }}</b></span></div>
      <div v-if="mode === 'questions'" class="heatmap-actions">
        <div class="heatmap-state-filters" role="group" :aria-label="uiText('按题目状态高亮')">
          <button v-for="state in (['all', 'unattempted', 'review', 'mastered', 'overdue'] as const)" v-show="state !== 'overdue' || hasOverdue" :key="state" type="button" :class="{ active: quickState === state }" :aria-pressed="quickState === state" @click="quickState = state">{{ state === 'all' ? uiText('全部') : state === 'unattempted' ? uiText('未做') : state === 'review' ? uiText('待复习') : state === 'mastered' ? uiText('已掌握') : uiText('逾期') }}</button>
        </div>
        <button type="button" class="heatmap-next" @click="locateNextUnattempted">{{ uiText('定位下一道未做题') }} <span aria-hidden="true">→</span></button>
      </div>
      <p v-if="locateMessage" class="heatmap-locate-message" role="status">{{ locateMessage }}</p>
      <section v-for="group in data.groups" :key="group.document_id" class="heatmap-group">
        <header class="heatmap-book-header">
          <div class="heatmap-book-title"><h2>{{ group.document }}</h2><small>{{ mode === 'topics' ? `${group.topics.length} 个考点` : `${group.questions.length} 题` }}</small></div>
          <div class="heatmap-book-stats"><strong>{{ group.statistics.coverage_percent }}%</strong><span>{{ uiText('已覆盖') }} {{ group.statistics.attempted_question_count }} {{ uiText('题') }}</span></div>
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
              <span>{{ uiText('考点预览') }} · {{ selectedTopic.document }}</span>
              <h3>{{ selectedTopic.topic.topic }}</h3>
              <p>{{ selectedTopic.topic.path }}</p>
            </div>
            <dl>
              <div><dt>{{ uiText('已覆盖') }}</dt><dd>{{ selectedTopic.topic.attempted_question_count }} / {{ selectedTopic.topic.question_count }}</dd></div>
              <div><dt>{{ uiText('作答次数') }}</dt><dd>{{ selectedTopic.topic.attempt_count }}</dd></div>
              <div><dt>{{ uiText('待复习') }}</dt><dd>{{ selectedTopic.topic.review_question_count }}</dd></div>
            </dl>
            <div class="topic-preview-actions">
              <button type="button" class="topic-preview-close" @click="selectedTopic = null">{{ uiText('关闭') }}</button>
              <button type="button" class="topic-preview-open" @click="openTopic(selectedTopic.documentId, selectedTopic.topic.topic_id)">{{ uiText('练习此考点') }} <b>→</b></button>
            </div>
          </aside>
        </Transition>
        <div v-if="mode === 'questions'" class="question-heatmap">
          <button
            v-for="(item, index) in group.questions"
            :key="item.uuid"
            :data-question-uuid="item.uuid" :data-type-group="item.type_group"
            :class="[item.review_overdue ? 'status-overdue' : `status-${item.state}`, { selected: selectedQuestion?.question.uuid === item.uuid, dimmed: !matchesQuickState(item) }]"
            :aria-pressed="selectedQuestion?.question.uuid === item.uuid"
            :aria-label="`${item.label}; ${item.state}; ${item.attempt_count} attempts`"
            :title="`${item.label} · ${item.core_topic || item.topic} · ${item.state} · ${item.attempt_count} attempts`"
            @click="previewQuestion(group.document_id, group.document, item)"
          ><span class="exam-heat-dot" :class="`exam-dot-${item.type_group || 'unknown'}`" /><span>{{ props.coreOnly ? index + 1 : item.year }}</span></button>
        </div>
        <Transition name="topic-preview">
          <aside v-if="mode === 'questions' && selectedQuestion?.documentId === group.document_id" class="topic-preview-card question-preview-card">
            <div class="topic-preview-copy">
              <span>{{ uiText('题目预览') }} · {{ selectedQuestion.document }}</span>
              <ExamTypeBadge :type="selectedQuestion.question.question_type" :group="selectedQuestion.question.type_group" /><h3>{{ selectedQuestion.question.label || `Question ${selectedQuestion.question.order}` }}</h3>
              <p>{{ selectedQuestion.question.core_topic || selectedQuestion.question.topic || uiText("General") }}<template v-if="selectedQuestion.question.year"> · {{ selectedQuestion.question.year }}{{ selectedQuestion.question.variant ? ` ${selectedQuestion.question.variant}` : '' }}</template></p>
            </div>
            <dl>
              <div><dt>{{ uiText('状态') }}</dt><dd>{{ selectedQuestion.question.review_overdue ? uiText('逾期') : selectedQuestion.question.state === 'mastered' ? uiText('已掌握') : selectedQuestion.question.state === 'review' ? uiText('待复习') : uiText('未做') }}</dd></div>
              <div><dt>{{ uiText('作答次数') }}</dt><dd>{{ selectedQuestion.question.attempt_count }}</dd></div>
              <div><dt>{{ uiText('序号') }}</dt><dd>{{ String(selectedQuestion.question.order).padStart(4, '0') }}</dd></div>
            </dl>
            <div class="topic-preview-actions">
              <button type="button" class="topic-preview-close" @click="selectedQuestion = null">{{ uiText('关闭') }}</button>
              <button type="button" class="topic-preview-open" @click="openQuestion(selectedQuestion.documentId, selectedQuestion.question)">{{ uiText('打开题目') }} <b>→</b></button>
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
.heat-mode, .heat-scope { display: flex; padding: 3px; border: 1px solid var(--border-subtle); border-radius: 8px; background: var(--bg-surface); }
.heat-mode button, .heat-scope button { min-height: 36px; padding: 0 12px; border: 0; border-radius: 6px; color: var(--text-secondary); background: transparent; font-size: 12px; cursor: pointer; }
.heat-mode button.active, .heat-scope button.active { color: var(--text-primary); background: var(--bg-elevated); }
.heat-legend { display: flex; flex-wrap: wrap; align-items: center; gap: 5px; color: var(--text-secondary); font-size: 12px; }
.heat-legend i { display: block; width: 10px; height: 10px; border: 1px solid var(--border-default); border-radius: 2px; }
.heat-legend i:not(:first-child) { margin-left: 8px; }
.heatmap-page :deep(.exam-type-controls) { margin: 8px 0 16px; }
.heatmap-page :deep(.exam-type-toolbar small) { display: none; }
.heatmap-page :deep(.exam-type-toolbar select), .heatmap-page :deep(.exam-small-entry) { min-height: 40px; }
@media (max-width: 700px) {
  .heatmap-page :deep(.exam-type-toolbar) { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; }
  .heatmap-page :deep(.exam-type-toolbar > label:first-child) { min-width: 0; }
  .heatmap-page :deep(.exam-type-toolbar select) { min-width: 0; max-width: 100%; }
  .heatmap-page :deep(.exam-type-toolbar > label:nth-of-type(2)) { grid-column: 1/-1; }
}
.heatmap-overview { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 12px; margin: 0 0 8px; color: var(--text-secondary); font-size: 13px; }
.heatmap-overview strong { color: var(--text-primary); font-size: 24px; font-weight: 650; line-height: 1; }
.heatmap-overview span:nth-of-type(n+2) { margin-left: 8px; }
.heatmap-overview b { color: var(--text-primary); font-weight: 600; }
.heatmap-actions { margin: 8px 0 16px; display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px 16px; }
.heatmap-state-filters { display: flex; flex-wrap: wrap; gap: 4px; }
.heatmap-state-filters button, .heatmap-next { min-height: 40px; padding: 0 12px; border: 1px solid transparent; border-radius: var(--radius-sm); color: var(--text-secondary); background: transparent; font-size: 13px; cursor: pointer; }
.heatmap-state-filters button:hover, .heatmap-next:hover { color: var(--text-primary); background: var(--bg-surface-hover); }
.heatmap-state-filters button.active { border-color: var(--border-default); color: var(--text-primary); background: var(--bg-elevated); }
.heatmap-next { border-color: var(--border-default); color: var(--accent); }
.heatmap-locate-message { margin: -8px 0 12px; color: var(--text-secondary); font-size: 13px; }
.heatmap-group { margin-top: 8px; padding: 16px; border: 1px solid var(--border-subtle); border-radius: 10px; background: var(--bg-surface); }
.heatmap-group > header { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; margin-bottom: 12px; gap: 12px; }
.heatmap-group h2 { margin: 0; font-size: 17px; line-height: 1.35; font-weight: 650; }
.heatmap-book-title { min-width: 0; }
.heatmap-book-title small { margin-top: 4px; color: var(--text-secondary); font-size: 12px; }
.heatmap-book-stats { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 12px; color: var(--text-secondary); font-size: 12px; }
.heatmap-book-stats strong { color: var(--text-primary); font-size: 16px; }
.topic-heatmap { display: grid; grid-template-columns: repeat(auto-fill, 26px); gap: 5px; }
.question-heatmap { display: grid; grid-template-columns: repeat(auto-fill, 28px); gap: 4px; }
.topic-heatmap button, .question-heatmap button { position: relative; width: 26px; height: 26px; padding: 0; border: 1px solid var(--border-default); border-radius: 4px; background: var(--bg-elevated); cursor: pointer; touch-action: manipulation; }
.question-heatmap button { width: 28px; height: 28px; }
.topic-heatmap button:active, .question-heatmap button:active { border-color: var(--accent); background: var(--bg-surface-active); }
.topic-heatmap button span, .question-heatmap button span { display: none; }
.topic-heatmap button:hover, .question-heatmap button:hover { border-color: var(--text-secondary); z-index: 1; }
.topic-heatmap button.selected, .question-heatmap button.selected { outline: 2px solid var(--accent); outline-offset: 2px; z-index: 1; }
.question-heatmap button.dimmed:not(.selected) { opacity: .3; }
.topic-heatmap button:focus-visible, .question-heatmap button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.topic-heatmap .intensity-1 { background: #23372c !important; }
.topic-heatmap .intensity-2 { background: #28503a !important; }
.topic-heatmap .intensity-3 { background: #326d48 !important; }
.topic-heatmap .intensity-4 { background: #43895c !important; }
:global([data-color-scheme="light"]) .topic-heatmap .intensity-1 { border-color: #a8cfb6 !important; background: #e1f2e7 !important; }
:global([data-color-scheme="light"]) .topic-heatmap .intensity-2 { border-color: #7ebd95 !important; background: #c8e8d3 !important; }
:global([data-color-scheme="light"]) .topic-heatmap .intensity-3 { border-color: #54a875 !important; background: #9fd8b3 !important; }
:global([data-color-scheme="light"]) .topic-heatmap .intensity-4 { border-color: #2f8554 !important; background: #70bf8d !important; }
.topic-preview-card { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; align-items: center; margin-top: 10px; padding: 16px; border: 1px solid var(--border-default); border-radius: var(--radius-md); background: var(--bg-elevated); gap: 16px; }
.topic-preview-copy { min-width: 0; }
.topic-preview-copy > span, .topic-preview-card dt { color: var(--text-secondary); font-size: 12px; }
.topic-preview-copy h3 { margin: 4px 0; overflow: hidden; font-size: 16px; text-overflow: ellipsis; white-space: nowrap; }
.topic-preview-copy p { margin: 0; overflow: hidden; color: var(--text-secondary); font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.topic-preview-card dl { display: flex; margin: 0; gap: 16px; }
.topic-preview-card dd { margin: 4px 0 0; color: var(--text-primary); font-size: 14px; font-variant-numeric: tabular-nums; }
.topic-preview-actions { display: flex; gap: 8px; }
.topic-preview-actions button { min-height: 40px; padding: 0 12px; border: 1px solid var(--border-default); border-radius: var(--radius-sm); color: var(--text-secondary); background: var(--bg-surface); font-size: 13px; cursor: pointer; }
.topic-preview-actions .topic-preview-open { border-color: var(--accent); color: var(--text-primary); background: var(--accent-muted); }
.topic-preview-enter-active, .topic-preview-leave-active { transition: opacity 140ms ease-out; }
.topic-preview-enter-from, .topic-preview-leave-to { opacity: 0; }
.exam-heat-dot { position:absolute; top:2px; right:2px; width:5px; height:5px; border-radius:50%; background:var(--text-secondary); }
.exam-dot-small { background:var(--accent); }.exam-dot-large { background:var(--warning); }.exam-dot-short_answer { background:#a895da; }

.core-controls { display: flex; flex-wrap: wrap; margin: 8px 0 16px; gap: 12px; }
.core-controls label { display: grid; min-width: 0; max-width: 100%; gap: 6px; color: var(--text-secondary); font-size: 13px; }
.core-controls select { min-height: 40px; min-width: 0; max-width: 100%; padding: 8px 10px; border: 1px solid var(--border-default); border-radius: var(--radius-sm); color: var(--text-primary); background: var(--bg-surface); }
.core-controls p { flex-basis: 100%; margin: 0; color: var(--text-secondary); font-size: 12px; line-height: 1.6; }
@media (max-width: 900px) {
  .heatmap-group > header { align-items: flex-start; }
  .topic-preview-card { grid-template-columns: minmax(0, 1fr) auto; }
  .topic-preview-actions { grid-column: 1 / -1; justify-content: flex-end; }
}
@media (max-width: 700px) {
  .heat-controls { justify-content: flex-start; }
  .heat-legend { display: flex; flex-wrap: wrap; }
  .heatmap-group { padding: 12px; }
  .topic-preview-card { grid-template-columns: 1fr; }
  .topic-preview-card dl { justify-content: space-between; }
  .heatmap-page .page-header { padding-left: 52px; }
}
</style>
