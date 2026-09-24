<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import { api, post, remove } from '../lib/api'
import { cachedNoteDraft, cachedQuestion, clearNoteDraft, fetchQuestion, patchQuestionState, prefetchQuestion, storeNoteDraft } from '../lib/workspace'
import type { QuestionDetail, QuestionMarkerCode, QuestionSummary } from '../types'
import MarkdownAnswer from '../components/MarkdownAnswer.vue'

const props = defineProps<{ uuid: string }>()
const router = useRouter()
const route = useRoute()
const note = ref('')
const markerOptions: Array<{ code: QuestionMarkerCode; label: string }> = [
  { code: 'overconfident', label: 'Overconfident' },
  { code: 'concept_gap', label: 'Concept Gap' },
  { code: 'rusty', label: 'Rusty' },
  { code: 'forgotten', label: 'Forgotten' },
]

function navigationQuery() {
  const query = router.currentRoute.value.query
  return Object.fromEntries(['document', 'topic', 'source_category', 'q', 'unattempted', 'marker']
    .filter((key) => query[key] !== undefined && query[key] !== '')
    .map((key) => [key, String(query[key])]))
}

function navigationQueryString() {
  return new URLSearchParams(navigationQuery()).toString()
}

function questionRouteQuery() {
  const query: Record<string, string> = navigationQuery()
  if (route.query.from === 'heatmap' || route.query.from === 'selected-heatmap') {
    query.from = String(route.query.from)
    query.heat_scope = String(route.query.heat_scope || 'all')
    query.heat_question = String(route.query.heat_question || props.uuid)
  } else if (route.query.from === 'collection') {
    query.from = 'collection'
    query.collection = String(route.query.collection || 'favorite')
  } else if (route.query.from === 'insight') {
    query.from = 'insight'
  }
  return query
}

function backToEntryPoint() {
  if (route.query.from === 'heatmap' || route.query.from === 'selected-heatmap') {
    void router.push({
      path: route.query.from === 'selected-heatmap' ? '/selected-heatmap' : '/heatmap',
      query: {
        mode: 'questions',
        scope: ['past_exam', 'mock_exam', 'all'].includes(String(route.query.heat_scope))
          ? String(route.query.heat_scope)
          : 'all',
        question: String(route.query.heat_question || props.uuid),
      },
    })
    return
  }
  if (route.query.from === 'collection') {
    void router.push(route.query.collection === 'review_later' ? '/review-later' : '/favorites')
    return
  }
  if (route.query.from === 'insight') {
    void router.push('/insight')
    return
  }
  void router.push({ path: '/practice', query: navigationQuery() })
}

const question = ref<QuestionDetail | null>(null)
const similar = ref<QuestionSummary[]>([])
const similarTopic = ref('')
const similarKind = ref<'' | 'past_exam' | 'practice'>('')
const similarCounts = ref({ past_exam: 0, practice: 0 })
const similarLoading = ref(false)
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const similarOpen = ref(false)
const answerOpen = ref(false)
const stateSaving = ref(false)
const noteSaveState = ref<'idle' | 'dirty' | 'saving' | 'saved'>('idle')
const markerSaving = ref(false)
const nextLoading = ref(false)

function questionAssets(loadedQuestion: QuestionDetail) {
  return loadedQuestion.question_assets || loadedQuestion.assets || []
}

function downloadAssets(kind: 'question' | 'answer', assets: QuestionDetail['answer_assets']) {
  if (!assets.length || !question.value) return
  const base = `${kind}-${question.value.display_label || `question-${question.value.question_order}`}`
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 64) || kind
  assets.forEach((asset, index) => {
    const link = document.createElement('a')
    link.href = asset.url
    link.download = `${base}${assets.length > 1 ? `-${String(index + 1).padStart(2, '0')}` : ''}.png`
    document.body.appendChild(link)
    link.click()
    link.remove()
  })
}
let loadSequence = 0
let noteDraftTimer = 0
let noteAutoSaveTimer = 0
let noteSavedTimer = 0
let noteDraftDirty = false
let questionOpenedAt = performance.now()
let questionTimerInterval = 0
let timingServerNow = 0
let timingStartsAt = 0
let timingSyncedAt = 0
let timingSyncPromise: Promise<void> | null = null
let timingSyncSequence = 0
const timingCountdown = ref(5)
const timingElapsedSeconds = ref(0)
const timingFinalized = ref(false)

const formattedQuestionTime = computed(() => {
  const seconds = timingElapsedSeconds.value
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const remainder = seconds % 60
  return hours
    ? `${hours}:${String(minutes).padStart(2, '0')}:${String(remainder).padStart(2, '0')}`
    : `${minutes}:${String(remainder).padStart(2, '0')}`
})

function updateQuestionTimer() {
  if (timingFinalized.value) return
  const now = timingServerNow
    ? timingServerNow + performance.now() - timingSyncedAt
    : performance.now()
  const startsAt = timingStartsAt || questionOpenedAt + 5000
  const elapsedMilliseconds = now - startsAt
  timingCountdown.value = Math.max(0, Math.ceil(-elapsedMilliseconds / 1000))
  timingElapsedSeconds.value = elapsedMilliseconds > 0
    ? Math.ceil(elapsedMilliseconds / 1000)
    : 0
}

function resetQuestionTimer() {
  window.clearInterval(questionTimerInterval)
  questionOpenedAt = performance.now()
  timingServerNow = 0
  timingStartsAt = 0
  timingSyncedAt = 0
  timingCountdown.value = 5
  timingElapsedSeconds.value = 0
  timingFinalized.value = false
  questionTimerInterval = window.setInterval(updateQuestionTimer, 500)
}

interface TimingResponse {
  server_now: string
  starts_at: string | null
}

function syncQuestionTimer(uuid: string) {
  const sequence = ++timingSyncSequence
  const request = post<TimingResponse>(`/api/drill/questions/${uuid}/timing/`, { action: 'begin' })
    .then((response) => {
      if (props.uuid !== uuid || !response.starts_at) return
      timingServerNow = new Date(response.server_now).getTime()
      timingStartsAt = new Date(response.starts_at).getTime()
      timingSyncedAt = performance.now()
      updateQuestionTimer()
    })
    .catch((reason) => { error.value = (reason as Error).message })
    .finally(() => {
      if (timingSyncSequence === sequence) timingSyncPromise = null
    })
  timingSyncPromise = request
  return request
}

async function cancelQuestionTimer(uuid: string) {
  if (timingFinalized.value) return
  try {
    if (timingSyncPromise) await timingSyncPromise
    await post<TimingResponse>(`/api/drill/questions/${uuid}/timing/`, { action: 'cancel' })
  } catch {
    // A cleanup failure must not trap the user on the current route.
  }
}

function recordedQuestionSeconds() {
  updateQuestionTimer()
  const seconds = timingElapsedSeconds.value
  return seconds >= 1 && seconds <= 43200 ? seconds : null
}

function formatRecordedDuration(seconds: number) {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const remainder = seconds % 60
  if (hours) return `${hours}h ${minutes}m ${remainder}s`
  if (minutes) return `${minutes}m ${remainder}s`
  return `${remainder}s`
}

function useQuestion(loadedQuestion: QuestionDetail) {
  question.value = {
    ...loadedQuestion,
    markers: loadedQuestion.markers || [],
    last_time_spent_seconds: loadedQuestion.last_time_spent_seconds ?? null,
    last_timed_at: loadedQuestion.last_timed_at ?? null,
    review_overdue: loadedQuestion.review_overdue ?? false,
  }
  const draft = cachedNoteDraft(props.uuid)
  note.value = draft === null ? loadedQuestion.note || '' : draft
  noteSaveState.value = draft !== null && draft !== (loadedQuestion.note || '') ? 'dirty' : 'idle'
}

function cacheNoteDraft() {
  window.clearTimeout(noteDraftTimer)
  window.clearTimeout(noteAutoSaveTimer)
  window.clearTimeout(noteSavedTimer)
  noteDraftDirty = true
  noteSaveState.value = 'dirty'
  const uuid = props.uuid
  const value = note.value
  noteDraftTimer = window.setTimeout(() => {
    storeNoteDraft(uuid, value)
    noteDraftDirty = false
  }, 300)
  noteAutoSaveTimer = window.setTimeout(() => {
    if (props.uuid === uuid && note.value === value) void saveNote()
  }, 5000)
}

function flushNoteDraft(uuid = props.uuid) {
  if (!noteDraftDirty) return
  window.clearTimeout(noteDraftTimer)
  storeNoteDraft(uuid, note.value)
  noteDraftDirty = false
}

function discardNoteDraft(uuid = props.uuid) {
  window.clearTimeout(noteDraftTimer)
  window.clearTimeout(noteAutoSaveTimer)
  noteDraftDirty = false
  clearNoteDraft(uuid)
}

function schedulePrefetch(loadedQuestion: QuestionDetail) {
  const query = navigationQueryString()
  void prefetchQuestion(loadedQuestion.next_question_uuid, query).then((nextQuestion) => {
    if (!nextQuestion?.next_question_uuid) return
    const connection = (navigator as Navigator & { connection?: { saveData?: boolean; effectiveType?: string } }).connection
    if (connection?.saveData || ['slow-2g', '2g'].includes(connection?.effectiveType || '')) return
    const idle = window.requestIdleCallback || ((callback: IdleRequestCallback) => window.setTimeout(callback, 600))
    idle(() => void prefetchQuestion(nextQuestion.next_question_uuid, query))
  })
  void prefetchQuestion(loadedQuestion.previous_question_uuid, query)
}

async function load() {
  const sequence = ++loadSequence
  const query = navigationQueryString()
  const cached = cachedQuestion(props.uuid, query)
  loading.value = !cached
  if (cached) useQuestion(cached)
  error.value = ''
  similarOpen.value = false
  answerOpen.value = false
  similar.value = []
  similarTopic.value = ''
  similarKind.value = ''
  similarCounts.value = { past_exam: 0, practice: 0 }
  try {
    const loadedQuestion = await fetchQuestion(props.uuid, query, Boolean(cached))
    if (sequence !== loadSequence) return
    useQuestion(loadedQuestion)
    schedulePrefetch(loadedQuestion)
  } catch (reason) {
    error.value = (reason as Error).message
  } finally {
    if (sequence === loadSequence) loading.value = false
  }
}

interface StateResponse {
  attempt_count: number
  latest_result: QuestionDetail['latest_result']
  state: QuestionDetail['state']
  can_undo: boolean
  confidence: number | null
  note: string | null
  is_favorite: boolean
  review_later: boolean
  review_overdue: boolean
  last_time_spent_seconds: number | null
  last_timed_at: string | null
}

function applyState(response: StateResponse) {
  if (!question.value) return
  question.value.attempt_count = response.attempt_count
  question.value.latest_result = response.latest_result
  question.value.state = response.state
  question.value.can_undo = response.can_undo
  question.value.confidence = response.confidence
  question.value.note = response.note
  question.value.saved_note = response.note || ''
  question.value.is_favorite = response.is_favorite
  question.value.review_later = response.review_later
  question.value.review_overdue = response.review_overdue
  question.value.last_time_spent_seconds = response.last_time_spent_seconds
  question.value.last_timed_at = response.last_timed_at
  note.value = response.note || ''
  patchQuestionState(props.uuid, response)
}

async function record(result: 'correct' | 'review' | 'reset') {
  saving.value = true
  try {
    const timeSpentSeconds = result === 'correct' || result === 'review'
      ? recordedQuestionSeconds()
      : null
    const response = await post<StateResponse>(`/api/drill/questions/${props.uuid}/attempts/`, {
      result,
      note: note.value,
      ...(timeSpentSeconds === null ? {} : { time_spent_seconds: timeSpentSeconds }),
    })
    discardNoteDraft()
    applyState(response)
    noteSaveState.value = 'idle'
    if (result === 'correct' || result === 'review') {
      timingFinalized.value = true
      window.clearInterval(questionTimerInterval)
    } else {
      resetQuestionTimer()
    }
    if (result === 'correct') await goToNext()
  } catch (reason) {
    error.value = (reason as Error).message
  } finally {
    saving.value = false
  }
}

interface UserStateResponse {
  note: string
  is_favorite: boolean
  review_later: boolean
  updated_at: string
}

async function saveUserState(update: Partial<Pick<UserStateResponse, 'is_favorite' | 'review_later'>>) {
  if (!question.value) return
  stateSaving.value = true
  try {
    const response = await post<UserStateResponse>(`/api/drill/questions/${props.uuid}/state/`, update)
    question.value.note = response.note
    question.value.saved_note = response.note
    question.value.is_favorite = response.is_favorite
    question.value.review_later = response.review_later
    patchQuestionState(props.uuid, response)
  } catch (reason) {
    error.value = (reason as Error).message
  } finally {
    stateSaving.value = false
  }
}

async function saveNote() {
  if (!question.value || noteSaveState.value === 'saving') return
  window.clearTimeout(noteAutoSaveTimer)
  window.clearTimeout(noteSavedTimer)
  const uuid = props.uuid
  const value = note.value
  noteSaveState.value = 'saving'
  try {
    const response = await post<UserStateResponse>(`/api/drill/questions/${uuid}/state/`, { note: value })
    if (props.uuid !== uuid || !question.value) return
    question.value.note = response.note
    question.value.saved_note = response.note
    question.value.is_favorite = response.is_favorite
    question.value.review_later = response.review_later
    patchQuestionState(uuid, response)
    if (note.value === value) {
      discardNoteDraft(uuid)
      noteSaveState.value = 'saved'
      noteSavedTimer = window.setTimeout(() => {
        if (noteSaveState.value === 'saved') noteSaveState.value = 'idle'
      }, 1800)
    } else {
      cacheNoteDraft()
    }
  } catch (reason) {
    noteSaveState.value = 'dirty'
    error.value = (reason as Error).message
  }
}

async function saveMarkers(codes: QuestionMarkerCode[]) {
  if (!question.value) return
  markerSaving.value = true
  try {
    const response = await post<{ markers: QuestionMarkerCode[] }>(`/api/drill/questions/${props.uuid}/markers/`, { codes })
    question.value.markers = response.markers
    patchQuestionState(props.uuid, { markers: response.markers })
  } catch (reason) {
    error.value = (reason as Error).message
  } finally {
    markerSaving.value = false
  }
}

function toggleMarker(code: QuestionMarkerCode) {
  if (!question.value) return
  const active = question.value.markers.includes(code)
  void saveMarkers(active
    ? question.value.markers.filter((item) => item !== code)
    : [...question.value.markers, code])
}

async function undo() {
  saving.value = true
  try {
    applyState(await remove<StateResponse>(`/api/drill/questions/${props.uuid}/attempts/`))
    resetQuestionTimer()
  } catch (reason) {
    error.value = (reason as Error).message
  } finally {
    saving.value = false
  }
}

async function showSimilar() {
  similarOpen.value = !similarOpen.value
  if (!similarOpen.value || similarTopic.value) return
  try {
    const response = await api<{ topic: string; counts: { past_exam: number; practice: number }; results: QuestionSummary[] }>(`/api/drill/questions/${props.uuid}/similar/`)
    similarTopic.value = response.topic
    similarCounts.value = response.counts
  } catch (reason) {
    error.value = (reason as Error).message
  }
}

async function loadSimilar(kind: 'past_exam' | 'practice') {
  similarKind.value = kind
  similarLoading.value = true
  similar.value = []
  try {
    const response = await api<{ topic: string; counts: { past_exam: number; practice: number }; results: QuestionSummary[] }>(`/api/drill/questions/${props.uuid}/similar/?kind=${kind}`)
    similarTopic.value = response.topic
    similarCounts.value = response.counts
    similar.value = response.results
  } catch (reason) {
    error.value = (reason as Error).message
  } finally {
    similarLoading.value = false
  }
}

async function goToNext(kind: 'sequential' | 'overdue' | 'review' = 'sequential') {
  if (!question.value || nextLoading.value) return
  nextLoading.value = true
  error.value = ''
  try {
    // Refresh navigation at click time so changes made in another tab/device
    // cannot send the user to a question that is now mastered.
    const refreshed = await fetchQuestion(props.uuid, navigationQueryString(), true)
    Object.assign(question.value, {
      next_question_uuid: refreshed.next_question_uuid,
      sequential_next_question_uuid: refreshed.sequential_next_question_uuid,
      next_overdue_review_uuid: refreshed.next_overdue_review_uuid,
      next_review_uuid: refreshed.next_review_uuid,
    })
    const target = kind === 'overdue'
      ? refreshed.next_overdue_review_uuid
      : kind === 'review'
        ? refreshed.next_review_uuid
        : refreshed.sequential_next_question_uuid
    if (!target) {
      error.value = kind === 'overdue'
        ? 'No overdue review questions remain.'
        : kind === 'review'
          ? 'No recent review questions remain.'
          : 'No next question remains in this source set.'
      return
    }
    await router.push({
      path: `/practice/${target}`,
      query: questionRouteQuery(),
    })
  } catch (reason) {
    error.value = (reason as Error).message
  } finally {
    nextLoading.value = false
  }
}

watch(() => props.uuid, (_uuid, previousUuid) => {
  window.clearTimeout(noteAutoSaveTimer)
  window.clearTimeout(noteSavedTimer)
  flushNoteDraft(previousUuid)
  noteSaveState.value = 'idle'
  resetQuestionTimer()
  void syncQuestionTimer(_uuid)
  void load()
})
onMounted(() => {
  resetQuestionTimer()
  void syncQuestionTimer(props.uuid)
  void load()
})
onUnmounted(() => {
  window.clearInterval(questionTimerInterval)
  window.clearTimeout(noteAutoSaveTimer)
  window.clearTimeout(noteSavedTimer)
  flushNoteDraft()
})

onBeforeRouteUpdate(async (to) => {
  if (String(to.params.uuid || '') !== props.uuid) await cancelQuestionTimer(props.uuid)
})
onBeforeRouteLeave(async () => {
  await cancelQuestionTimer(props.uuid)
})
</script>

<template>
  <section class="page question-page">
    <button class="back-link" @click="backToEntryPoint">← {{ route.query.from === 'selected-heatmap' ? 'Back to selected heatmap' : route.query.from === 'heatmap' ? 'Back to heatmap' : route.query.from === 'collection' ? 'Back to saved questions' : route.query.from === 'insight' ? 'Back to insight' : 'Question bank' }}</button>
    <p v-if="error" class="error-state">{{ error }}</p>
    <div v-if="loading" class="question-skeleton">LOADING QUESTION…</div>
    <template v-else-if="question">
      <header class="question-header">
        <div><span class="eyebrow">{{ question.document }} · {{ String(question.question_order).padStart(4, '0') }}</span><h1>{{ question.display_label || `Question ${question.question_order}` }}</h1><p>{{ question.breadcrumbs.map((item) => item.title).join(' / ') }}</p><div class="question-badges"><span class="source-badge" :class="`category-${question.source_category}`">{{ question.source_category_label }}</span><span v-if="question.record_kind === 'grouped'" class="source-badge">Grouped source extract</span></div></div>
        <div class="attempt-counter"><span>CURRENT STATE</span><strong class="state-name" :class="question.review_overdue ? 'text-overdue' : `text-${question.state}`">{{ question.review_overdue ? 'OVERDUE REVIEW' : question.state === 'mastered' ? 'MASTERED' : question.state === 'review' ? 'REVIEW' : 'NOT STARTED' }}</strong><small>{{ question.attempt_count }} recorded attempts</small><small v-if="question.last_time_spent_seconds !== null" class="last-solving-time">Last time · {{ formatRecordedDuration(question.last_time_spent_seconds) }}</small></div>
      </header>

      <nav class="question-nav"><button :disabled="!question.previous_question_uuid" @click="question.previous_question_uuid && router.push({ path: `/practice/${question.previous_question_uuid}`, query: questionRouteQuery() })">← Previous</button><button :disabled="!question.sequential_next_question_uuid || nextLoading" @click="goToNext('sequential')">{{ nextLoading ? 'Finding next…' : 'Next →' }}</button></nav>

      <div class="question-save-actions">
        <button type="button" :class="{ active: question.is_favorite }" :disabled="stateSaving" @click="saveUserState({ is_favorite: !question.is_favorite })"><b>{{ question.is_favorite ? '★' : '☆' }}</b>{{ question.is_favorite ? 'Favorited' : 'Favorite' }}</button>
        <button type="button" :class="{ active: question.review_later }" :disabled="stateSaving" @click="saveUserState({ review_later: !question.review_later })"><b>↻</b>{{ question.review_later ? 'Added to next time' : 'Add to next time' }}</button>
      </div>

      <div class="question-workbench">
        <div class="question-problem-pane">
          <div v-if="questionAssets(question).length" class="asset-toolbar question-asset-toolbar">
            <button type="button" @click="downloadAssets('question', questionAssets(question))">Save question image</button>
          </div>
          <article class="question-canvas">
            <img v-for="asset in questionAssets(question)" :key="asset.id" :src="asset.url" :width="asset.width" :height="asset.height" alt="Question content" loading="eager" decoding="async" />
            <MarkdownAnswer v-if="!questionAssets(question).length" class="question-markdown" :source="question.prompt_text" />
          </article>

          <section v-if="question.has_answer || question.answer_markdown" class="official-answer">
            <button class="answer-toggle" :aria-expanded="answerOpen" @click="answerOpen = !answerOpen">
              <span>{{ answerOpen ? 'Hide answer' : (question.has_answer ? 'Show answer' : 'Show Agent solution') }}</span><b>{{ answerOpen ? '↑' : '↓' }}</b>
            </button>
            <div v-if="answerOpen" class="answer-canvas">
              <div v-if="question.answer_assets.length" class="asset-toolbar answer-asset-toolbar">
                <button type="button" @click="downloadAssets('answer', question.answer_assets)">Save answer image</button>
              </div>
              <img v-for="asset in question.answer_assets" :key="asset.id" :src="asset.url" :width="asset.width" :height="asset.height" alt="Official answer" loading="lazy" decoding="async" />
              <div v-if="question.answer_markdown" class="agent-answer-block">
                <header><strong>{{ question.answer_source === 'provided-reference' ? 'REFERENCE ANSWER' : 'AGENT SOLUTION' }}</strong><span>{{ question.answer_source || 'agent' }} · {{ question.answer_confidence === null ? 'unrated' : `${Math.round(question.answer_confidence * 100)}% confidence` }}</span></header>
                <MarkdownAnswer :source="question.answer_markdown" />
              </div>
            </div>
          </section>
        </div>

        <aside class="question-control-pane">
          <div class="answer-bar">
            <div><div class="question-timer" :class="{ active: !timingCountdown && !timingFinalized, saved: timingFinalized }"><span>{{ timingFinalized ? 'TIME SAVED' : timingCountdown ? 'TIMER READY' : 'SOLVING TIME' }}</span><strong>{{ timingFinalized || !timingCountdown ? formattedQuestionTime : `Starts in ${timingCountdown}s` }}</strong></div><span>QUESTION STATE</span><small>Grey = not started, green = mastered, yellow = needs review. You can change, reset, or undo at any time.</small><label class="note-field">Note <textarea v-model="note" maxlength="2000" placeholder="Optional note" @input="cacheNoteDraft" /><span class="note-controls"><small class="note-draft-hint">{{ noteSaveState === 'saving' ? 'Saving to server…' : noteSaveState === 'saved' ? 'Saved to server.' : 'Autosaves after 5 seconds without changes.' }}</small><button type="button" class="save-note" :disabled="noteSaveState === 'saving'" @click="saveNote">{{ noteSaveState === 'saving' ? 'Saving…' : noteSaveState === 'saved' ? 'Saved ✓' : 'Save note' }}</button></span></label></div>
            <div><button class="review" :class="{ selected: question.state === 'review' }" :disabled="saving" @click="record('review')">Needs review</button><button class="correct" :class="{ selected: question.state === 'mastered' }" :disabled="saving" @click="record('correct')">Mastered</button><button :disabled="saving || question.state === 'unattempted'" @click="record('reset')">Reset</button><button :disabled="saving || !question.can_undo" @click="undo">Undo</button></div>
          </div>

          <div class="next-question-group">
            <button class="next-question sequential" :disabled="!question.sequential_next_question_uuid || nextLoading" @click="goToNext('sequential')"><span>{{ nextLoading ? 'Finding next question…' : 'Next in sequence' }}</span><small>Continue in source order across topics and books</small><b>→</b></button>
            <button class="next-question overdue" aria-label="Open the next overdue red review question" title="Next overdue review" :disabled="!question.next_overdue_review_uuid || nextLoading" @click="goToNext('overdue')"><span>Next red review</span><small>Waiting 5+ days</small><b>→</b></button>
            <button class="next-question review" aria-label="Open the next yellow review question" title="Next recent review" :disabled="!question.next_review_uuid || nextLoading" @click="goToNext('review')"><span>Next yellow review</span><small>Within 5 days</small><b>→</b></button>
          </div>

          <details v-if="question.source_label && question.source_label !== question.display_label" class="raw-provenance"><summary>View original imported label</summary><code>{{ question.source_label }}</code></details>

          <button class="similar-trigger" @click="showSimilar"><span>Practice similar questions</span><small>Same indexed knowledge topic</small><b>{{ similarOpen ? '↓' : '→' }}</b></button>
          <section v-if="similarOpen" class="similar-panel">
            <header><span>SIMILAR SET</span><strong>{{ similarTopic || 'No indexed topic' }}</strong></header>
            <div class="similar-kind-picker">
              <button :class="{ selected: similarKind === 'past_exam' }" :disabled="!similarCounts.past_exam" @click="loadSimilar('past_exam')"><span>OFFICIAL PAST EXAMS</span><strong>{{ similarCounts.past_exam }}</strong><small>Verified exam-source questions</small></button>
              <button :class="{ selected: similarKind === 'practice' }" :disabled="!similarCounts.practice" @click="loadSimilar('practice')"><span>MOCK / PRACTICE</span><strong>{{ similarCounts.practice }}</strong><small>Workbooks, mock papers and other practice</small></button>
            </div>
            <p v-if="!similarKind">Choose which source type to practise.</p>
            <p v-else-if="similarLoading">LOADING SIMILAR QUESTIONS…</p>
            <button v-for="item in similar" :key="item.uuid" @click="router.push({ path: `/practice/${item.uuid}`, query: questionRouteQuery() })"><span>{{ item.display_label || `Question ${item.question_order}` }}</span><small>{{ item.document }} · {{ item.state }} · {{ item.attempt_count }} attempts</small><b>→</b></button>
            <p v-if="similarKind && !similarLoading && !similar.length">No questions of this source type were indexed for this topic.</p>
          </section>

          <section class="learning-markers">
            <header><div><span>LEARNING SIGNALS</span><small>Independent from question state. Select any that apply.</small></div><div><button type="button" :disabled="markerSaving" @click="saveMarkers(markerOptions.map((item) => item.code))">All</button><button type="button" :disabled="markerSaving || !question.markers.length" @click="saveMarkers([])">Clear</button></div></header>
            <div><button v-for="marker in markerOptions" :key="marker.code" type="button" :class="{ active: question.markers.includes(marker.code) }" :disabled="markerSaving" @click="toggleMarker(marker.code)">{{ marker.label }}</button></div>
          </section>
        </aside>
      </div>
    </template>
  </section>
</template>
