<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../lib/api'
import { cachedHeatmap, storeHeatmap } from '../lib/workspace'

interface HeatmapQuestion {
  uuid: string
  order: number
  label: string
  topic: string
  year: number | null
  variant: string
  attempt_count: number
  latest_result: string | null
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
  state: 'unattempted' | 'progress' | 'mastered' | 'review'
}

interface HeatmapPayload {
  question_count: number
  topic_count: number
  groups: Array<{
    document_id: number
    document: string
    questions: HeatmapQuestion[]
    topics: HeatmapTopic[]
  }>
}

const router = useRouter()
const route = useRoute()
const data = ref<HeatmapPayload | null>(null)
const loading = ref(true)
const error = ref('')
const initialScope = ['past_exam', 'mock_exam', 'all'].includes(String(route.query.scope))
  ? String(route.query.scope) as 'past_exam' | 'mock_exam' | 'all'
  : 'all'
const initialMode = ['topics', 'questions'].includes(String(route.query.mode))
  ? String(route.query.mode) as 'topics' | 'questions'
  : 'topics'
const scope = ref<'past_exam' | 'mock_exam' | 'all'>(initialScope)
const mode = ref<'topics' | 'questions'>(initialMode)
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

function previewTopic(documentId: number, document: string, topic: HeatmapTopic) {
  selectedQuestion.value = null
  selectedTopic.value = { documentId, document, topic }
}

function previewQuestion(documentId: number, document: string, question: HeatmapQuestion) {
  selectedTopic.value = null
  selectedQuestion.value = { documentId, document, question }
}

function openTopic(documentId: number, topicId: number) {
  void router.push({
    path: '/practice',
    query: { document: String(documentId), topic: String(topicId) },
  })
}

function openQuestion(documentId: number, question: HeatmapQuestion) {
  sessionStorage.setItem(returnStateKey, JSON.stringify({
    scope: scope.value,
    questionUuid: question.uuid,
    scrollY: window.scrollY,
  }))
  const query: Record<string, string> = {
    document: String(documentId),
    from: 'heatmap',
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

async function load() {
  const requestedScope = scope.value
  const requestedMode = mode.value
  const cacheKey = `${requestedMode}:${requestedScope}`
  const cached = cachedHeatmap<HeatmapPayload>(cacheKey)
  if (cached) {
    data.value = cached
    void restoreQuestionSelection(cached)
  }
  loading.value = !cached
  error.value = ''
  try {
    const value = await api<HeatmapPayload>(`/api/drill/heatmap/?scope=${requestedScope}&mode=${requestedMode}`)
    if (scope.value !== requestedScope || mode.value !== requestedMode) return
    data.value = value
    storeHeatmap(cacheKey, value)
    void restoreQuestionSelection(value)
  } catch (reason) {
    error.value = (reason as Error).message
  } finally {
    if (scope.value === requestedScope && mode.value === requestedMode) loading.value = false
  }
}

watch([scope, mode], () => {
  selectedTopic.value = null
  selectedQuestion.value = null
  pendingQuestionUuid = ''
  void load()
})
onMounted(load)
</script>

<template>
  <section class="page heatmap-page">
    <header class="page-header">
      <div><span class="eyebrow">Knowledge map</span><h1>Coverage by book</h1><p>Every topic and question cell opens a preview before navigation.</p></div>
      <div class="heat-controls">
        <div class="heat-mode"><button :class="{ active: mode === 'topics' }" @click="mode = 'topics'">Topics</button><button :class="{ active: mode === 'questions' }" @click="mode = 'questions'">Questions</button></div>
        <div class="heat-scope"><button :class="{ active: scope === 'all' }" @click="scope = 'all'">All</button><button :class="{ active: scope === 'past_exam' }" @click="scope = 'past_exam'">Past exams</button><button :class="{ active: scope === 'mock_exam' }" @click="scope = 'mock_exam'">Mock exams</button></div>
        <div class="heat-legend"><i class="status-unattempted" /><span>NOT STARTED</span><i class="status-progress" /><span>IN PROGRESS</span><i class="status-mastered" /><span>MASTERED</span><i class="status-review" /><span>REVIEW</span></div>
      </div>
    </header>
    <p v-if="error" class="error-state">{{ error }}</p>
    <div v-else-if="loading" class="question-skeleton">BUILDING HEATMAP…</div>
    <template v-else-if="data">
      <div class="heatmap-summary"><strong>{{ mode === 'topics' ? data.topic_count : data.question_count }}</strong><span>{{ mode === 'topics' ? 'indexed knowledge topics across all visible books' : scope === 'past_exam' ? 'verified official past-exam records' : scope === 'mock_exam' ? 'mock-exam records' : 'all practiceable records' }}</span></div>
      <section v-for="group in data.groups" :key="group.document_id" class="heatmap-group">
        <header><div><span>BOOK</span><h2>{{ group.document }}</h2></div><strong>{{ mode === 'topics' ? `${group.topics.length} topics` : `${group.questions.length} questions` }}</strong></header>
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
            v-for="item in group.questions"
            :key="item.uuid"
            :data-question-uuid="item.uuid"
            :class="[`status-${item.state}`, { selected: selectedQuestion?.question.uuid === item.uuid }]"
            :aria-pressed="selectedQuestion?.question.uuid === item.uuid"
            :aria-label="`${item.label}; ${item.state}; ${item.attempt_count} attempts`"
            :title="`${item.label} · ${item.topic} · ${item.state} · ${item.attempt_count} attempts`"
            @click="previewQuestion(group.document_id, group.document, item)"
          ><span>{{ item.year }}</span></button>
        </div>
        <Transition name="topic-preview">
          <aside v-if="mode === 'questions' && selectedQuestion?.documentId === group.document_id" class="topic-preview-card question-preview-card">
            <div class="topic-preview-copy">
              <span>QUESTION PREVIEW · {{ selectedQuestion.document }}</span>
              <h3>{{ selectedQuestion.question.label || `Question ${selectedQuestion.question.order}` }}</h3>
              <p>{{ selectedQuestion.question.topic || 'General' }}<template v-if="selectedQuestion.question.year"> · {{ selectedQuestion.question.year }}{{ selectedQuestion.question.variant ? ` ${selectedQuestion.question.variant}` : '' }}</template></p>
            </div>
            <dl>
              <div><dt>STATE</dt><dd>{{ selectedQuestion.question.state === 'mastered' ? 'MASTERED' : selectedQuestion.question.state === 'review' ? 'REVIEW' : 'NOT STARTED' }}</dd></div>
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
    </template>
  </section>
</template>
