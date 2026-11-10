<script setup lang="ts">
import { uiText } from '../lib/uiText'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import { api, ApiError, post, remove } from '../lib/api'
import { cachedNoteDraft, cachedQuestion, clearNoteDraft, fetchQuestion, patchQuestionState, prefetchQuestion, storeNoteDraft, warmQuestionMedia } from '../lib/workspace'
import type { AttemptDiagnosis, ErrorCode, QuestionDetail, QuestionSummary } from '../types'
import ExamTypeEditor from '../components/ExamTypeEditor.vue'
import NoteVisibility from '../components/NoteVisibility.vue'
import { typeText } from '../lib/examTypes'
import MarkdownAnswer from '../components/MarkdownAnswer.vue'
import SourcePaperViewer from '../components/SourcePaperViewer.vue'
import OriginalAnswer from '../components/OriginalAnswer.vue'
import { sourcePracticeTarget } from '../lib/sourcePractice'
import { circuitFilters } from '../lib/circuitSelected'
import { createAndCopyShare, createAndCopyShareOnGesture } from '../lib/share'
import { notifyPracticeTrendChanged } from '../lib/practiceTrend'
import { emptyNextQuestionMessage, emptyPreviousQuestionMessage, nextQuestionTarget, previousQuestionTarget, type NextQuestionMode } from '../lib/questionNavigation'
import { runtimeWorkspace, withWorkspacePrefix } from '../lib/runtimePath'
import { buildClipboardPng, copyImagesToClipboard, downloadImageBlob, shareImageBlob } from '../lib/imageClipboard'
import { useUiPreferences } from '../lib/uiPreferences'

const props = defineProps<{ uuid: string }>()
const { t } = useUiPreferences()
const router = useRouter()
const route = useRoute()
const note = ref('')
const errorOptions: Array<{ code: ErrorCode; label: string; group: string }> = [
  { code: 'A', label: '知识断层', group: 'A' },
  { code: 'B1', label: '想不起来', group: 'B' },
  { code: 'B2', label: '不会启动', group: 'B' },
  { code: 'B3', label: '不会组合', group: 'B' },
  { code: 'C1', label: '计算错误', group: 'C' },
  { code: 'C2', label: '符号/方向/单位', group: 'C' },
  { code: 'C3', label: '边界/条件错误', group: 'C' },
  { code: 'D', label: '看解析仍不懂', group: 'D' },
]

function navigationQuery() {
  const query = router.currentRoute.value.query
  return Object.fromEntries(['type_group', 'exam_type', 'document', 'topic', 'source_category', 'q', 'unattempted', 'marker', 'collection', 'bucket', 'tier', 'kind', 'material', 'combined', 'state', 'scope', 'course', 'mode', 'insight_return', 'insight_list', 'collection_page', 'from']
    .filter((key) => query[key] !== undefined && query[key] !== '')
    .map((key) => [key, String(query[key])]))
}

function navigationQueryString() {
  return new URLSearchParams(navigationQuery()).toString()
}

function questionRouteQuery() {
  const query: Record<string, string> = navigationQuery()
  if (route.query.from === 'core-heatmap') { query.from = 'core-heatmap'; return query }
  if (['circuit-selected', 'signal-selected', 'analog-selected', 'digital-selected', 'communication-selected'].includes(String(route.query.from))) {
    query.from = String(route.query.from)
    return query
  }
  if (route.query.from === 'heatmap' || route.query.from === 'selected-heatmap') {
    query.from = String(route.query.from)
    query.heat_scope = String(route.query.heat_scope || 'all')
    query.heat_question = String(route.query.heat_question || props.uuid)
  } else if (route.query.from === 'collection') {
    query.from = 'collection'
    query.collection = String(route.query.collection || 'favorite')
  } else if (route.query.from === 'insight') {
    query.from = 'insight'
  } else if (route.query.from === 'diagnostics') {
    query.from = 'diagnostics'
  } else if (route.query.from === 'cockpit') {
    query.from = 'cockpit'
  }
  return query
}

function backToEntryPoint() {
  if (route.query.from === 'core-heatmap') {
    void router.push({ path: '/core-heatmap', query: { type_group: String(route.query.type_group || ''), scope: String(route.query.scope || 'all'), course: String(route.query.course || ''), material: String(route.query.material || 'ready'), question: props.uuid } })
    return
  }
  if (['circuit-selected', 'signal-selected', 'analog-selected', 'digital-selected', 'communication-selected'].includes(String(route.query.from))) {
    void router.push({ path: '/' + route.query.from, query: { ...circuitFilters(route.query), all: '1', question: props.uuid } })
    return
  }
  if (route.query.from === 'heatmap' || route.query.from === 'selected-heatmap') {
    void router.push({
      path: route.query.from === 'selected-heatmap' ? '/selected-heatmap' : '/heatmap',
      query: {
        mode: 'questions', type_group: String(route.query.type_group || ''),
        scope: ['past_exam', 'mock_exam', 'all'].includes(String(route.query.heat_scope))
          ? String(route.query.heat_scope)
          : 'all',
        question: String(route.query.heat_question || props.uuid),
      },
    })
    return
  }
  if (route.query.from === 'collection') {
    void router.push({ path: route.query.collection === 'review_later' ? '/review-later' : '/favorites', query: { page: String(route.query.collection_page || '1') } })
    return
  }
  if (route.query.from === 'insight') {
    const target = String(route.query.insight_return || '')
    void router.push(target.startsWith('/insight') ? target : '/insight')
    return
  }
  if (route.query.from === 'diagnostics') {
    void router.push('/diagnostics')
    return
  }
  if (route.query.from === 'cockpit') {
    void router.push('/cockpit')
    return
  }
  void router.push({ path: '/practice', query: navigationQuery() })
}

const question = ref<QuestionDetail | null>(null)
const navigationFrame = ref<{ uuid: string; previous: string | null; next: string | null }>({
  uuid: props.uuid, previous: null, next: null,
})
const navigationPrevious = computed(() => question.value ? question.value.previous_question_uuid
  : navigationFrame.value.uuid === props.uuid ? navigationFrame.value.previous : null)
const navigationNext = computed(() => question.value ? question.value.sequential_next_question_uuid
  : navigationFrame.value.uuid === props.uuid ? navigationFrame.value.next : null)
const topPreviousTarget = computed(() => question.value
  ? previousQuestionTarget(question.value, nextMode.value)
  : nextMode.value === 'sequential' ? navigationPrevious.value : null)
const topNextTarget = computed(() => question.value
  ? nextQuestionTarget(question.value, nextMode.value)
  : nextMode.value === 'sequential' ? navigationNext.value : null)
const topPreviousLabel = computed(() => ({
  sequential: '上一题', overdue: '上一道红色题', review: '上一道黄色题',
})[nextMode.value])
const topNextLabel = computed(() => question.value ? ({
  sequential: '下一题', overdue: '下一道到期题', review: '下一道待复习题',
})[nextMode.value] : '下一题')
const sourceViewer = ref<InstanceType<typeof SourcePaperViewer> | null>(null)

function navigateToQuestion(uuid: string | null, direction: 'previous' | 'next', copyArmed = false) {
  if (!uuid) return
  if (!copyArmed) startPageTurnCopy(Promise.resolve(uuid))
  const cached = cachedQuestion(uuid, navigationQueryString())
  navigationFrame.value = cached ? {
    uuid,
    previous: cached.previous_question_uuid,
    next: cached.sequential_next_question_uuid,
  } : {
    uuid,
    previous: direction === 'next' ? props.uuid : null,
    next: direction === 'previous' ? props.uuid : null,
  }
  void router.push({ path: `/practice/${uuid}`, query: questionRouteQuery() })
}

function selectSourceQuestion(uuid: string) {
  void router.push({ path: `/practice/${uuid}`, query: questionRouteQuery() })
}
const similar = ref<QuestionSummary[]>([])
const similarTopic = ref('')
const similarKind = ref<'' | 'past_exam' | 'practice'>('')
const similarCounts = ref({ past_exam: 0, practice: 0 })
const similarLoading = ref(false)
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const errorStatus = ref<number | null>(null)
const similarOpen = ref(false)
const answerOpen = ref(false)
const answerViewedThisRound = ref(false)
const usedHintThisRound = ref(false)
const diagnosisOpen = ref(localStorage.getItem(`${runtimeWorkspace}.diagnosis-open.v1`) === 'true')
const selectedErrors = ref<ErrorCode[]>([])
const primaryError = ref<ErrorCode | null>(null)
const knowledgeLevel = ref<'K0' | 'K1' | 'K2' | null>(null)
const methodLevel = ref<'M0' | 'M1' | 'M2' | null>(null)
const executionLevel = ref<'E0' | 'E1' | 'E2' | null>(null)
const pendingSubmissionKey = ref<string | null>(null)
const historyOpen = ref(false)
const historyLoading = ref(false)
const attemptHistory = ref<AttemptDiagnosis[]>([])
const editingAttemptId = ref<number | null>(null)
const diagnosisSaveState = ref<'idle' | 'draft' | 'saving' | 'saved' | 'error'>('idle')
const stateSaving = ref(false)
const noteSaveState = ref<'idle' | 'dirty' | 'saving' | 'saved' | 'error'>('idle')
const noteOpen = ref(false)
const nextLoading = ref(false)
const erratumOpen = ref(false)
const erratumKind = ref('crop')
const erratumDescription = ref('')
const erratumSaving = ref(false)
const erratumMessage = ref('')
const shareState = ref<'idle' | 'sharing' | 'copied'>('idle')
const imageCopyState = ref<'idle' | 'copying' | 'copied' | 'fallback'>('idle')
const imageCopyMessage = ref('')
const pageTurnCopyMessage = ref('')
const pageTurnCopyFailed = ref(false)
const clipboardImage = ref<Blob | null>(null)
const actionFeedback = ref('')
const nextMode = ref<NextQuestionMode>((localStorage.getItem('drill.next-mode.v1') as NextQuestionMode) || 'sequential')
type PageTurnCopyMode = 'off' | 'link' | 'image'
const pageTurnCopyStorageKey = `${runtimeWorkspace}.page-turn-copy.v1`
const storedPageTurnCopyMode = localStorage.getItem(pageTurnCopyStorageKey)
const pageTurnCopyMode = ref<PageTurnCopyMode>(
  storedPageTurnCopyMode === 'link' || storedPageTurnCopyMode === 'image' ? storedPageTurnCopyMode : 'off',
)
const autoCopyLink = computed({
  get: () => pageTurnCopyMode.value === 'link',
  set: (enabled: boolean) => { pageTurnCopyMode.value = enabled ? 'link' : 'off' },
})
const autoCopyImage = computed({
  get: () => pageTurnCopyMode.value === 'image',
  set: (enabled: boolean) => { pageTurnCopyMode.value = enabled ? 'image' : 'off' },
})
const reviewAutoNext = ref(localStorage.getItem('drill.review-auto-next.v1') === 'true')
const masteredAutoNext = ref(localStorage.getItem('drill.mastered-auto-next.v1') !== 'false')

watch(nextMode, (value) => localStorage.setItem('drill.next-mode.v1', value))
watch(diagnosisOpen, (value) => localStorage.setItem(`${runtimeWorkspace}.diagnosis-open.v1`, String(value)))
watch(pageTurnCopyMode, (value) => localStorage.setItem(pageTurnCopyStorageKey, value))
watch(reviewAutoNext, (value) => localStorage.setItem('drill.review-auto-next.v1', String(value)))
watch(masteredAutoNext, (value) => localStorage.setItem('drill.mastered-auto-next.v1', String(value)))

let pageTurnCopySequence = 0
let pageTurnCopyFeedbackTimer = 0

watch(pageTurnCopyMessage, (message) => {
  window.clearTimeout(pageTurnCopyFeedbackTimer)
  if (message && !message.startsWith('正在')) {
    pageTurnCopyFeedbackTimer = window.setTimeout(() => { pageTurnCopyMessage.value = '' },
      pageTurnCopyFailed.value ? 8000 : 3500)
  }
})

function startPageTurnCopy(target: Promise<string>): boolean {
  const mode = pageTurnCopyMode.value
  if (mode === 'off') return false
  const sequence = ++pageTurnCopySequence
  const query = navigationQueryString()
  pageTurnCopyFailed.value = false
  pageTurnCopyMessage.value = mode === 'link' ? '正在自动复制分享链接…' : '正在自动复制题图…'
  if (mode === 'link') {
    const endpoint = target.then((uuid) => `/api/drill/questions/${uuid}/share/`)
    void createAndCopyShareOnGesture(endpoint).then(({ copied }) => {
      if (sequence !== pageTurnCopySequence) return
      pageTurnCopyFailed.value = !copied
      pageTurnCopyMessage.value = copied
        ? '当前题分享链接已自动复制 ✓'
        : '浏览器阻止了自动复制；请点击上方「复制分享链接」重试。'
    }).catch((reason) => {
      if (sequence !== pageTurnCopySequence) return
      pageTurnCopyFailed.value = true
      pageTurnCopyMessage.value = `分享链接未复制：${(reason as Error).message}`
    })
  } else {
    const urls = target.then((uuid) => fetchQuestion(uuid, query, true)).then((loaded) =>
      questionAssets(loaded).map((asset) => withWorkspacePrefix(asset.url)))
    void urls.catch(() => { /* Clipboard API may reject before awaiting URLs. */ })
    void copyImagesToClipboard(urls).then((result) => {
      if (sequence !== pageTurnCopySequence) return
      pageTurnCopyMessage.value = result.combined
        ? '当前题的多张题图已拼接并自动复制 ✓'
        : '当前题题图已自动复制 ✓'
    }).catch((reason) => {
      if (sequence !== pageTurnCopySequence) return
      pageTurnCopyFailed.value = true
      pageTurnCopyMessage.value = `题图未自动复制：${(reason as Error).message} 请点击题图上方「复制题图」重试。`
    })
  }
  return true
}

async function shareQuestion() {
  if (shareState.value === 'sharing') return
  const uuid = props.uuid
  shareState.value = 'sharing'
  try {
    await createAndCopyShare(`/api/drill/questions/${uuid}/share/`)
    if (props.uuid !== uuid) return
    shareState.value = 'copied'
    window.setTimeout(() => {
      if (props.uuid === uuid) shareState.value = 'idle'
    }, 2500)
  } catch (reason) {
    if (props.uuid !== uuid) return
    shareState.value = 'idle'
    error.value = (reason as Error).message
  }
}

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
    link.href = withWorkspacePrefix(asset.url)
    link.download = `${base}${assets.length > 1 ? `-${String(index + 1).padStart(2, '0')}` : ''}.png`
    document.body.appendChild(link)
    link.click()
    link.remove()
  })
}

function questionImageFilename() {
  const label = question.value?.display_label || `question-${question.value?.question_order || ''}`
  const safe = label.toLowerCase().replace(/[^a-z0-9\u4e00-\u9fff]+/g, '-').replace(/^-|-$/g, '').slice(0, 64)
  return `${safe || 'question'}.png`
}

function questionImageUrls() {
  return question.value ? questionAssets(question.value).map((asset) => withWorkspacePrefix(asset.url)) : []
}

async function copyQuestionImages() {
  if (!question.value || imageCopyState.value === 'copying') return
  imageCopyState.value = 'copying'
  imageCopyMessage.value = ''
  clipboardImage.value = null
  try {
    const result = await copyImagesToClipboard(questionImageUrls())
    clipboardImage.value = result.blob
    imageCopyState.value = 'copied'
    imageCopyMessage.value = result.combined ? '多张题图已纵向拼接并复制 ✓' : '已复制题图 ✓'
    window.setTimeout(() => { if (imageCopyState.value === 'copied') imageCopyState.value = 'idle' }, 2600)
  } catch (reason) {
    try {
      clipboardImage.value = (await buildClipboardPng(questionImageUrls())).blob
    } catch { /* Original download remains available below. */ }
    imageCopyState.value = 'fallback'
    imageCopyMessage.value = (reason as Error).message
  }
}

async function shareQuestionImage() {
  try {
    const blob = clipboardImage.value || (await buildClipboardPng(questionImageUrls())).blob
    clipboardImage.value = blob
    await shareImageBlob(blob, questionImageFilename())
  } catch (reason) {
    imageCopyMessage.value = (reason as Error).message
  }
}

async function downloadQuestionImage() {
  try {
    const blob = clipboardImage.value || (await buildClipboardPng(questionImageUrls())).blob
    clipboardImage.value = blob
    downloadImageBlob(blob, questionImageFilename())
  } catch (reason) {
    imageCopyMessage.value = (reason as Error).message
    if (question.value) downloadAssets('question', questionAssets(question.value))
  }
}
let loadSequence = 0
let loadController: AbortController | null = null
let operationSequence = 0
let noteDraftTimer = 0
let noteAutoSaveTimer = 0
let noteSavedTimer = 0
let diagnosisSaveTimer = 0
let diagnosisSaveSequence = 0
let diagnosisHydrating = false
let actionFeedbackTimer = 0
let noteDraftDirty = false
let questionOpenedAt = performance.now()
let questionTimerInterval = 0
let timingServerNow = 0
let timingStartsAt = 0
let timingSyncedAt = 0
let timingSyncPromise: Promise<void> | null = null
let timingSyncSequence = 0
let timingClientKey = crypto.randomUUID()
const timingCountdown = ref(5)
const timingElapsedSeconds = ref(0)
const timingFinalized = ref(false)
const failedImages = ref<Record<string, boolean>>({})
const imageRetryTokens = ref<Record<string, number>>({})

function imageUrl(url: string) {
  const workspaceUrl = withWorkspacePrefix(url)
  const retry = imageRetryTokens.value[url] || 0
  if (!retry) return workspaceUrl
  return `${workspaceUrl}${workspaceUrl.includes('?') ? '&' : '?'}retry=${retry}`
}

function markImageFailed(url: string) {
  failedImages.value = { ...failedImages.value, [url]: true }
}

function retryImage(url: string) {
  failedImages.value = { ...failedImages.value, [url]: false }
  imageRetryTokens.value = { ...imageRetryTokens.value, [url]: Date.now() }
}

function toggleNote(event: Event) {
  noteOpen.value = Boolean((event.currentTarget as HTMLDetailsElement).open)
}

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
  const request = post<TimingResponse>(`/api/drill/questions/${uuid}/timing/`, {
    action: 'begin', timing_key: timingClientKey,
  })
    .then((response) => {
      if (props.uuid !== uuid || !response.starts_at) return
      timingServerNow = new Date(response.server_now).getTime()
      timingStartsAt = new Date(response.starts_at).getTime()
      timingSyncedAt = performance.now()
      updateQuestionTimer()
    })
    .catch((reason) => {
      if (props.uuid === uuid) error.value = (reason as Error).message
    })
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
    await post<TimingResponse>(`/api/drill/questions/${uuid}/timing/`, {
      action: 'cancel', timing_key: timingClientKey,
    })
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
  // A saved Note is visible immediately in the compact preview. Only expand
  // automatically for a local draft that may still need attention.
  noteOpen.value = draft !== null
  navigationFrame.value = {
    uuid: loadedQuestion.uuid,
    previous: loadedQuestion.previous_question_uuid,
    next: loadedQuestion.sequential_next_question_uuid,
  }
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
  // The visible question image is loaded by the DOM; warm its answer now so
  // opening the answer is instant. Adjacent prefetches warm both prompt and
  // answer media for previous, next, and next-next questions.
  warmQuestionMedia(loadedQuestion)
  // `sequential_next_question_uuid` is the actual target of the primary Next
  // button. It can differ from `next_question_uuid` when mastered questions
  // are skipped or navigation crosses a topic/book boundary.
  void prefetchQuestion(loadedQuestion.sequential_next_question_uuid, query).then((nextQuestion) => {
    if (!nextQuestion?.sequential_next_question_uuid) return
    const connection = (navigator as Navigator & { connection?: { saveData?: boolean; effectiveType?: string } }).connection
    if (connection?.saveData || ['slow-2g', '2g'].includes(connection?.effectiveType || '')) return
    const idle = window.requestIdleCallback || ((callback: IdleRequestCallback) => window.setTimeout(callback, 600))
    idle(() => void prefetchQuestion(nextQuestion.sequential_next_question_uuid, query))
  })
  // Keep the alternate unmastered target warm for state-driven flows too.
  if (loadedQuestion.next_question_uuid !== loadedQuestion.sequential_next_question_uuid) {
    void prefetchQuestion(loadedQuestion.next_question_uuid, query)
  }
  void prefetchQuestion(loadedQuestion.previous_question_uuid, query)
  void prefetchQuestion(loadedQuestion.next_overdue_review_uuid, query)
  void prefetchQuestion(loadedQuestion.next_review_uuid, query)
}

async function load() {
  loadController?.abort()
  loadController = new AbortController()
  const controller = loadController
  const sequence = ++loadSequence
  const uuid = props.uuid
  const query = navigationQueryString()
  const cached = cachedQuestion(props.uuid, query)
  loading.value = !cached
  if (cached) useQuestion(cached)
  else question.value = null
  error.value = ''
  errorStatus.value = null
  similarOpen.value = false
  answerOpen.value = false
  answerViewedThisRound.value = false
  usedHintThisRound.value = false
  diagnosisHydrating = true
  selectedErrors.value = []
  primaryError.value = null
  knowledgeLevel.value = null
  methodLevel.value = null
  executionLevel.value = null
  diagnosisHydrating = false
  diagnosisSaveState.value = 'idle'
  pendingSubmissionKey.value = null
  historyOpen.value = false
  attemptHistory.value = []
  editingAttemptId.value = null
  similar.value = []
  similarTopic.value = ''
  similarKind.value = ''
  similarCounts.value = { past_exam: 0, practice: 0 }
  try {
    const loadedQuestion = await fetchQuestion(uuid, query, Boolean(cached), controller.signal)
    if (sequence !== loadSequence) return
    const individualUuid = sourcePracticeTarget(loadedQuestion, route.query.view)
    if (individualUuid) {
      await router.replace({ path: `/practice/${individualUuid}`, query: questionRouteQuery() })
      return
    }
    useQuestion(loadedQuestion)
    schedulePrefetch(loadedQuestion)
  } catch (reason) {
    if (sequence !== loadSequence || (reason as Error).name === 'AbortError') return
    error.value = (reason as Error).message
    errorStatus.value = reason instanceof ApiError ? reason.status : 0
    if (sequence === loadSequence) question.value = null
  } finally {
    if (sequence === loadSequence) {
      loading.value = false
      if (loadController === controller) loadController = null
    }
  }
}

interface StateResponse {
  attempt_count: number
  latest_result: QuestionDetail['latest_result']
  state: QuestionDetail['state']
  can_undo: boolean
  confidence: number | null
  note: string | null
  state_version: number
  note_conflict?: boolean
  is_favorite: boolean
  review_later: boolean
  review_overdue: boolean
  last_time_spent_seconds: number | null
  last_timed_at: string | null
  latest_diagnosis?: QuestionDetail['latest_diagnosis']
  review_plan?: QuestionDetail['review_plan']
}

function applyState(response: StateResponse, uuid = props.uuid) {
  patchQuestionState(uuid, response)
  if (props.uuid !== uuid || !question.value || question.value.uuid !== uuid) return
  question.value.attempt_count = response.attempt_count
  question.value.latest_result = response.latest_result
  question.value.state = response.state
  const sourcePin = question.value.source_context?.anchors.find((item) => item.uuid === question.value?.uuid)
  if (sourcePin) sourcePin.state = response.state
  question.value.can_undo = response.can_undo
  question.value.confidence = response.confidence
  question.value.note = response.note
  question.value.state_version = response.state_version
  question.value.saved_note = response.note || ''
  question.value.is_favorite = response.is_favorite
  question.value.review_later = response.review_later
  question.value.review_overdue = response.review_overdue
  question.value.last_time_spent_seconds = response.last_time_spent_seconds
  question.value.last_timed_at = response.last_timed_at
  if (response.latest_diagnosis !== undefined) question.value.latest_diagnosis = response.latest_diagnosis
  if (response.review_plan !== undefined) question.value.review_plan = response.review_plan
  note.value = response.note || ''
}

async function record(result: 'correct' | 'review' | 'reset') {
  if (saving.value || !question.value) return
  window.clearTimeout(diagnosisSaveTimer)
  diagnosisSaveSequence += 1
  const uuid = props.uuid
  const sequence = ++operationSequence
  saving.value = true
  const submittedNote = note.value
  const willTurn = (result === 'correct' && masteredAutoNext.value)
    || (result === 'review' && reviewAutoNext.value)
  let pendingCopy: { resolve: (uuid: string) => void; reject: (reason: Error) => void } | null = null
  let copyArmed = false
  if (willTurn && pageTurnCopyMode.value !== 'off' && topNextTarget.value) {
    const deferred = {} as { resolve: (uuid: string) => void; reject: (reason: Error) => void }
    const target = new Promise<string>((resolve, reject) => {
      deferred.resolve = resolve
      deferred.reject = reject
    })
    pendingCopy = deferred
    copyArmed = startPageTurnCopy(target)
  }
  try {
    const timeSpentSeconds = result === 'correct' || result === 'review'
      ? recordedQuestionSeconds()
      : null
    if (!pendingSubmissionKey.value) pendingSubmissionKey.value = crypto.randomUUID()
    const response = await post<StateResponse>(`/api/drill/questions/${uuid}/attempts/`, {
      result,
      note: note.value,
      state_version: question.value?.state_version || undefined,
      timing_key: timingClientKey,
      submission_key: pendingSubmissionKey.value,
      ...(result === 'correct' || result === 'review' ? {
        is_independent: !usedHintThisRound.value && !answerViewedThisRound.value,
        used_hint: usedHintThisRound.value,
        viewed_answer: answerViewedThisRound.value,
        judgement_source: 'self',
        knowledge_level: knowledgeLevel.value,
        method_level: methodLevel.value,
        execution_level: executionLevel.value,
        error_codes: result === 'review' ? selectedErrors.value : [],
        primary_error: result === 'review' ? primaryError.value : null,
      } : {}),
      ...(timeSpentSeconds === null ? {} : { time_spent_seconds: timeSpentSeconds }),
    })
    if (sequence !== operationSequence) return
    pendingSubmissionKey.value = null
    if (!response.note_conflict) discardNoteDraft(uuid)
    applyState(response, uuid)
    notifyPracticeTrendChanged()
    if (props.uuid !== uuid) return
    editingAttemptId.value = null
    diagnosisSaveState.value = result === 'correct' || result === 'review' ? 'saved' : 'idle'
    if (result === 'correct' || result === 'review') {
      window.clearTimeout(actionFeedbackTimer)
      actionFeedback.value = result === 'correct' ? '已保存：掌握状态与本轮诊断' : '已保存：待复习状态与本轮诊断'
      actionFeedbackTimer = window.setTimeout(() => { actionFeedback.value = '' }, 1800)
    }
    noteSaveState.value = response.note_conflict ? 'error' : 'idle'
    if (response.note_conflict) {
      note.value = submittedNote
      storeNoteDraft(uuid, submittedNote)
      error.value = '作答已保存，但笔记在另一标签页被更新；本地草稿已保留，请确认后再保存。'
    }
    if (result === 'correct' || result === 'review') {
      timingFinalized.value = true
      window.clearInterval(questionTimerInterval)
    } else {
      resetQuestionTimer()
    }
    if (willTurn) {
      const target = question.value ? nextQuestionTarget(question.value, nextMode.value) : null
      if (target) pendingCopy?.resolve(target)
      else pendingCopy?.reject(new Error(emptyNextQuestionMessage(nextMode.value)))
      pendingCopy = null
      await goToNext(nextMode.value, copyArmed)
    }
  } catch (reason) {
    if (props.uuid === uuid && sequence === operationSequence) error.value = (reason as Error).message
  } finally {
    pendingCopy?.reject(new Error('作答未完成，已取消自动复制。'))
    if (sequence === operationSequence) saving.value = false
  }
}

function toggleError(code: ErrorCode) {
  if (selectedErrors.value.includes(code)) {
    selectedErrors.value = selectedErrors.value.filter((item) => item !== code)
    if (primaryError.value === code) primaryError.value = selectedErrors.value[0] || null
  } else {
    selectedErrors.value = [...selectedErrors.value, code]
    if (!primaryError.value) primaryError.value = code
  }
}

function diagnosisPayload() {
  return {
    error_codes: selectedErrors.value,
    primary_error: primaryError.value,
    knowledge_level: knowledgeLevel.value,
    method_level: methodLevel.value,
    execution_level: executionLevel.value,
    used_hint: usedHintThisRound.value,
    viewed_answer: answerViewedThisRound.value,
    is_independent: !usedHintThisRound.value && !answerViewedThisRound.value,
  }
}

function diagnosisChanged() {
  if (diagnosisHydrating) return
  window.clearTimeout(diagnosisSaveTimer)
  diagnosisSaveSequence += 1
  if (!editingAttemptId.value) {
    diagnosisSaveState.value = 'draft'
    return
  }
  const uuid = props.uuid
  const attemptId = editingAttemptId.value
  const sequence = diagnosisSaveSequence
  diagnosisSaveState.value = 'draft'
  diagnosisSaveTimer = window.setTimeout(async () => {
    diagnosisSaveState.value = 'saving'
    try {
      const updated = await api<AttemptDiagnosis>(`/api/drill/attempts/${attemptId}/diagnosis/`, {
        method: 'PATCH', body: JSON.stringify(diagnosisPayload()),
      })
      if (props.uuid !== uuid || sequence !== diagnosisSaveSequence) return
      attemptHistory.value = attemptHistory.value.map((item) => item.id === updated.id ? updated : item)
      if (question.value?.latest_diagnosis?.id === updated.id) question.value.latest_diagnosis = updated
      diagnosisSaveState.value = 'saved'
    } catch (reason) {
      if (props.uuid === uuid && sequence === diagnosisSaveSequence) {
        diagnosisSaveState.value = 'error'
        error.value = (reason as Error).message
      }
    }
  }, 550)
}

watch([
  selectedErrors, primaryError, knowledgeLevel, methodLevel, executionLevel,
  usedHintThisRound, answerViewedThisRound,
], diagnosisChanged, { flush: 'sync' })

function toggleUsedHint() {
  usedHintThisRound.value = !usedHintThisRound.value
}

function toggleAnswer() {
  answerOpen.value = !answerOpen.value
  if (answerOpen.value) answerViewedThisRound.value = true
}

async function loadAttemptHistory() {
  historyOpen.value = !historyOpen.value
  if (historyOpen.value) diagnosisOpen.value = true
  if (!historyOpen.value || attemptHistory.value.length || historyLoading.value) return
  historyLoading.value = true
  const uuid = props.uuid
  try {
    const payload = await api<{ results: AttemptDiagnosis[] }>(`/api/drill/questions/${uuid}/attempts/`)
    if (props.uuid !== uuid) return
    attemptHistory.value = payload.results
  } catch (reason) {
    if (props.uuid === uuid) error.value = (reason as Error).message
  } finally {
    if (props.uuid === uuid) historyLoading.value = false
  }
}

function editDiagnosis(attempt: AttemptDiagnosis) {
  diagnosisHydrating = true
  editingAttemptId.value = attempt.id
  selectedErrors.value = attempt.errors.map((item) => item.code)
  primaryError.value = attempt.primary_error
  knowledgeLevel.value = attempt.knowledge_level
  methodLevel.value = attempt.method_level
  executionLevel.value = attempt.execution_level
  usedHintThisRound.value = attempt.used_hint === true
  answerViewedThisRound.value = attempt.viewed_answer === true
  diagnosisSaveState.value = 'idle'
  diagnosisHydrating = false
  diagnosisOpen.value = true
}

interface UserStateResponse {
  note: string
  is_favorite: boolean
  review_later: boolean
  updated_at: string
  version: number
}

async function saveUserState(update: Partial<Pick<UserStateResponse, 'is_favorite' | 'review_later'>>) {
  if (!question.value) return
  const uuid = props.uuid
  const version = question.value.state_version || undefined
  stateSaving.value = true
  try {
    const response = await post<UserStateResponse>(`/api/drill/questions/${uuid}/state/`, {
      ...update, version,
    })
    patchQuestionState(uuid, { ...response, state_version: response.version })
    if (props.uuid !== uuid || !question.value || question.value.uuid !== uuid) return
    question.value.note = response.note
    question.value.saved_note = response.note
    question.value.is_favorite = response.is_favorite
    question.value.review_later = response.review_later
    question.value.state_version = response.version
  } catch (reason) {
    if (props.uuid !== uuid) return
    if (reason instanceof ApiError && reason.status === 409 && question.value) {
      const serverVersion = Number(reason.body.version || 0)
      if (serverVersion) question.value.state_version = serverVersion
      if (typeof reason.body.is_favorite === 'boolean') question.value.is_favorite = reason.body.is_favorite
      if (typeof reason.body.review_later === 'boolean') question.value.review_later = reason.body.review_later
      if (typeof reason.body.note === 'string') {
        question.value.saved_note = reason.body.note
        if (noteSaveState.value === 'idle' || noteSaveState.value === 'saved') {
          question.value.note = reason.body.note
          note.value = reason.body.note
        }
      }
    }
    error.value = (reason as Error).message
  } finally {
    if (props.uuid === uuid) stateSaving.value = false
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
    const response = await post<UserStateResponse>(`/api/drill/questions/${uuid}/state/`, {
      note: value, version: question.value.state_version || undefined,
    })
    if (props.uuid !== uuid || !question.value) return
    question.value.note = response.note
    question.value.saved_note = response.note
    question.value.is_favorite = response.is_favorite
    question.value.review_later = response.review_later
    question.value.state_version = response.version
    patchQuestionState(uuid, { ...response, state_version: response.version })
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
    if (props.uuid !== uuid) return
    noteSaveState.value = 'error'
    storeNoteDraft(uuid, value)
    if (reason instanceof ApiError && reason.status === 409) {
      const serverVersion = Number(reason.body.version || 0)
      if (serverVersion && question.value) question.value.state_version = serverVersion
    }
    error.value = (reason as Error).message
  }
}

async function submitErratum() {
  const description = erratumDescription.value.trim()
  if (!description || erratumSaving.value) return
  erratumSaving.value = true
  const uuid = props.uuid
  erratumMessage.value = ''
  try {
    await post('/api/drill/errata/', { question_uuid: uuid, kind: erratumKind.value, description })
    if (props.uuid !== uuid) return
    erratumDescription.value = ''
    erratumMessage.value = '勘误已提交，可在勘误列表查看。'
  } catch (reason) {
    if (props.uuid === uuid) erratumMessage.value = (reason as Error).message
  } finally {
    if (props.uuid === uuid) erratumSaving.value = false
  }
}

async function undo() {
  if (saving.value || !question.value) return
  const uuid = props.uuid
  const sequence = ++operationSequence
  saving.value = true
  try {
    const response = await remove<StateResponse>(`/api/drill/questions/${uuid}/attempts/`)
    if (sequence !== operationSequence) return
    applyState(response, uuid)
    notifyPracticeTrendChanged()
    if (props.uuid === uuid) resetQuestionTimer()
  } catch (reason) {
    if (props.uuid === uuid && sequence === operationSequence) error.value = (reason as Error).message
  } finally {
    if (sequence === operationSequence) saving.value = false
  }
}

async function showSimilar() {
  similarOpen.value = !similarOpen.value
  if (!similarOpen.value || similarTopic.value) return
  const uuid = props.uuid
  try {
    const response = await api<{ topic: string; counts: { past_exam: number; practice: number }; results: QuestionSummary[] }>(`/api/drill/questions/${uuid}/similar/`)
    if (props.uuid !== uuid) return
    similarTopic.value = response.topic
    similarCounts.value = response.counts
  } catch (reason) {
    if (props.uuid === uuid) error.value = (reason as Error).message
  }
}

async function loadSimilar(kind: 'past_exam' | 'practice') {
  const uuid = props.uuid
  similarKind.value = kind
  similarLoading.value = true
  similar.value = []
  try {
    const response = await api<{ topic: string; counts: { past_exam: number; practice: number }; results: QuestionSummary[] }>(`/api/drill/questions/${uuid}/similar/?kind=${kind}`)
    if (props.uuid !== uuid || similarKind.value !== kind) return
    similarTopic.value = response.topic
    similarCounts.value = response.counts
    similar.value = response.results
  } catch (reason) {
    if (props.uuid === uuid) error.value = (reason as Error).message
  } finally {
    if (props.uuid === uuid && similarKind.value === kind) similarLoading.value = false
  }
}

function goToPrevious() {
  const target = topPreviousTarget.value
  if (!target) {
    error.value = emptyPreviousQuestionMessage(nextMode.value)
    return
  }
  navigateToQuestion(target, 'previous')
}

async function goToNext(kind: NextQuestionMode = 'sequential', copyArmed = false) {
  if (nextLoading.value) return
  const uuid = props.uuid
  error.value = ''
  // Navigation targets and their media are prefetched while the current
  // question is open. Do not put another API round-trip in the click path.
  const target = question.value
    ? nextQuestionTarget(question.value, kind)
    : navigationNext.value
  if (!target) {
    error.value = emptyNextQuestionMessage(kind)
    return
  }
  nextLoading.value = true
  try {
    navigateToQuestion(target, 'next', copyArmed)
  } catch (reason) {
    if (props.uuid === uuid) error.value = `无法进入下一题：${(reason as Error).message}`
  } finally {
    if (props.uuid === uuid) nextLoading.value = false
  }
}

watch(() => props.uuid, (_uuid, previousUuid) => {
  loadController?.abort()
  operationSequence += 1
  saving.value = false
  stateSaving.value = false
  similarLoading.value = false
  nextLoading.value = false
  window.clearTimeout(diagnosisSaveTimer)
  diagnosisSaveSequence += 1
  diagnosisSaveState.value = 'idle'
  window.clearTimeout(noteAutoSaveTimer)
  window.clearTimeout(noteSavedTimer)
  flushNoteDraft(previousUuid)
  noteSaveState.value = 'idle'
  timingClientKey = crypto.randomUUID()
  resetQuestionTimer()
  void syncQuestionTimer(_uuid)
  void load()
})

function refreshAfterPageRestore(event: PageTransitionEvent) {
  if (!event.persisted) return
  operationSequence += 1
  void load()
}

onMounted(() => {
  window.addEventListener('pageshow', refreshAfterPageRestore)
  resetQuestionTimer()
  void syncQuestionTimer(props.uuid)
  void load()
})
onUnmounted(() => {
  window.removeEventListener('pageshow', refreshAfterPageRestore)
  loadController?.abort()
  window.clearInterval(questionTimerInterval)
  window.clearTimeout(noteAutoSaveTimer)
  window.clearTimeout(noteSavedTimer)
  window.clearTimeout(diagnosisSaveTimer)
  window.clearTimeout(actionFeedbackTimer)
  window.clearTimeout(pageTurnCopyFeedbackTimer)
  flushNoteDraft()
})

onBeforeRouteUpdate((to) => {
  // Persist cleanup in parallel. Waiting for this POST made every prefetched
  // Next transition feel like a network navigation.
  if (String(to.params.uuid || '') !== props.uuid) void cancelQuestionTimer(props.uuid)
})
onBeforeRouteLeave(() => {
  void cancelQuestionTimer(props.uuid)
})
</script>

<template>
  <section class="page question-page">
    <p v-if="actionFeedback" class="action-feedback" role="status">✓ {{ uiText(actionFeedback) }}</p>
    <p v-if="pageTurnCopyMessage" class="page-turn-copy-feedback" :class="{ error: pageTurnCopyFailed }" role="status">{{ uiText(pageTurnCopyMessage) }}</p>
    <nav class="question-topbar" :aria-label="uiText('题目导航')">
      <button class="question-return" type="button" @click="backToEntryPoint">← {{ route.query.from === 'core-heatmap' ? uiText("五科核心热力图") : route.query.from === 'communication-selected' ? uiText("通信严选") : route.query.from === 'digital-selected' ? uiText("数电严选") : route.query.from === 'analog-selected' ? uiText("模电严选") : route.query.from === 'signal-selected' ? uiText("信号严选") : route.query.from === 'circuit-selected' ? uiText("电路严选") : route.query.from === 'selected-heatmap' ? uiText("严选题热力图") : route.query.from === 'heatmap' ? uiText("热力图") : route.query.from === 'collection' ? uiText("收藏题目") : route.query.from === 'insight' ? t('insight') : route.query.from === 'cockpit' ? uiText("892 总览") : uiText("题库") }}</button>
      <div class="question-page-turner">
        <button type="button" :disabled="!topPreviousTarget" @click="goToPrevious">← {{ uiText(topPreviousLabel) }}</button>
        <span v-if="loading">{{ uiText("正在加载当前题") }}</span>
        <button class="next" type="button" :disabled="!topNextTarget || nextLoading" @click="goToNext(nextMode)">{{ nextLoading ? uiText("切换中…") : `${uiText(topNextLabel)} →` }}</button>
      </div>
    </nav>
    <section v-if="error && !question" class="question-load-error" role="alert">
      <span>{{ errorStatus === 404 ? uiText("题目不存在 · 404") : errorStatus === 403 ? uiText("无访问权限 · 403") : errorStatus === 409 ? uiText("数据冲突 · 409") : errorStatus === 429 ? uiText("请求过于频繁 · 429") : errorStatus && errorStatus >= 500 ? uiText("服务器暂时不可用") : uiText("网络请求失败") }}</span>
      <h1>{{ uiText(error) }}</h1>
      <p>{{ uiText("不会显示上一题来冒充当前题；已成功提交的作答不会因本页加载失败而丢失。") }}</p>
      <div><button type="button" @click="load">{{ uiText("重试") }}</button><button type="button" @click="backToEntryPoint">{{ uiText("返回题库") }}</button><button type="button" :disabled="!topPreviousTarget" @click="goToPrevious">{{ uiText("返回") }}{{ uiText(topPreviousLabel) }}</button></div>
    </section>
    <p v-else-if="error" class="error-state">{{ uiText(error) }}</p>
    <div v-if="loading" class="question-skeleton">{{ uiText("正在加载题目…") }}</div>
    <template v-else-if="question">
      <header class="question-header">
        <div><span class="eyebrow">{{ question.document }} · {{ String(question.question_order).padStart(4, '0') }}</span><h1>{{ question.display_label || `${typeText('题目', 'Question')} ${question.question_order}` }}</h1><p>{{ question.breadcrumbs.map((item) => item.title).join(' / ') }}</p><div class="question-badges"><ExamTypeEditor :key="question.uuid" :question="question" @saved="(patch) => { if (question) { Object.assign(question, patch); patchQuestionState(question.uuid, patch) } }" /><span class="source-badge" :class="`category-${question.source_category}`">{{ question.source_category_label }}</span><span v-if="question.record_kind === 'grouped'" class="source-badge">{{ uiText("组合题源节选") }}</span></div><p v-if="question.pdf_pages" class="pdf-page-reference">{{ uiText("PDF 绝对页码 · 题目册") }} {{ question.pdf_pages.question }} {{ uiText("· 答案册") }} {{ question.pdf_pages.answer }} {{ uiText("· 题答对照册") }} {{ question.pdf_pages.paired }}</p></div>
        <div class="attempt-counter"><span>{{ uiText("当前状态") }}</span><strong class="state-name" :class="question.review_overdue ? 'text-overdue' : `text-${question.state}`">{{ question.review_overdue ? uiText("复习已到期") : question.state === 'mastered' ? uiText("已掌握") : question.state === 'review' ? uiText("待复习") : uiText("未开始") }}</strong><small>{{ uiText("已记录") }} {{ question.attempt_count }} {{ uiText("次作答") }}</small><small v-if="question.last_time_spent_seconds !== null" class="last-solving-time">{{ uiText("上次用时 ·") }} {{ formatRecordedDuration(question.last_time_spent_seconds) }}</small></div>
      </header>

      <div class="question-save-actions" :aria-label="uiText('题目工具')">
        <button type="button" :class="{ active: question.is_favorite }" :disabled="stateSaving" @click="saveUserState({ is_favorite: !question.is_favorite })"><b>{{ question.is_favorite ? '★' : '☆' }}</b>{{ question.is_favorite ? uiText("已收藏") : uiText("收藏") }}</button>
        <button type="button" :disabled="shareState === 'sharing'" @click="shareQuestion"><b>↗</b>{{ shareState === 'sharing' ? uiText("正在生成…") : shareState === 'copied' ? uiText("链接已复制 ✓") : uiText("复制分享链接") }}</button>
        <button type="button" :class="{ active: question.review_later }" :disabled="stateSaving" @click="saveUserState({ review_later: !question.review_later })"><b>↻</b>{{ question.review_later ? uiText("已加入下次复习") : uiText("加入下次复习") }}</button>
        <button type="button" :class="{ active: erratumOpen }" @click="erratumOpen = !erratumOpen"><b>!</b>{{ uiText("提交勘误") }}</button>
      </div>

      <div class="question-workbench">
        <div class="question-problem-pane">
          <p v-if="question.source_review_warning" role="note" class="source-review-warning">{{ question.source_review_warning }}</p>
          <p v-if="question.original_source" class="source-original-link"><RouterLink :to="{ path: `/practice/${question.original_source.uuid}`, query: { ...questionRouteQuery(), view: 'original' } }">{{ uiText("查看完整原卷／原页（原始题图已保留） ↗") }}</RouterLink></p>
          <nav v-if="question.source_context" class="source-tracking-toolbar" :aria-label="uiText('当前小题掌握情况')">
            <strong>{{ question.display_label }}</strong>
            <button @click="sourceViewer?.scrollToCurrent()">{{ uiText("定位本题") }}</button>
          </nav>
          <div v-if="questionAssets(question).length" class="asset-toolbar question-asset-toolbar">
            <button class="copy-question-image" type="button" :disabled="imageCopyState === 'copying'" @click="copyQuestionImages">{{ imageCopyState === 'copying' ? uiText("正在复制…") : imageCopyState === 'copied' ? uiText("已复制题图 ✓") : uiText("复制题图") }}</button>
            <span v-if="imageCopyMessage" :class="{ error: imageCopyState === 'fallback' }">{{ uiText(imageCopyMessage) }}</span>
            <template v-if="imageCopyState === 'fallback'"><button type="button" @click="shareQuestionImage">{{ uiText("系统分享") }}</button><button type="button" @click="downloadQuestionImage">{{ uiText("下载 PNG") }}</button></template>
          </div>
          <article class="question-canvas" :class="{ 'source-canvas': question.source_context, 'individual-source-canvas': question.original_source, 'fit-question-images': !question.source_context && questionAssets(question).length > 0 }">
            <SourcePaperViewer v-if="question.source_context" ref="sourceViewer" :question="question" @select="selectSourceQuestion" />
            <template v-else>
              <template v-for="asset in questionAssets(question)" :key="asset.id">
                <img v-show="!failedImages[asset.url]" :src="imageUrl(asset.url)" :width="asset.width" :height="asset.height" :alt="uiText('题目内容')" loading="eager" decoding="async" @error="markImageFailed(asset.url)" />
                <div v-if="failedImages[asset.url]" class="asset-load-error" role="alert"><span>{{ uiText("题目图片加载失败") }}</span><button type="button" @click="retryImage(asset.url)">{{ uiText("重新加载图片") }}</button></div>
              </template>
            </template>
            <MarkdownAnswer v-if="!questionAssets(question).length" class="question-markdown" :source="question.prompt_text" />
          </article>

        </div>

        <aside class="question-control-pane" tabindex="0" :aria-label="typeText('作答与笔记', 'Answers and notes')">
          <section v-if="erratumOpen" class="erratum-compose">
            <header><div><strong>{{ uiText("提交勘误") }}</strong><small>{{ uiText("同一工作区的用户都可以看到。") }}</small></div><RouterLink to="/errata">{{ uiText("查看全部勘误 →") }}</RouterLink></header>
            <div><select v-model="erratumKind" :aria-label="uiText('勘误类型')"><option value="crop">{{ uiText("图片或裁切") }}</option><option value="question">{{ uiText("题目内容") }}</option><option value="answer">{{ uiText("答案或解析") }}</option><option value="formula">{{ uiText("公式显示") }}</option><option value="metadata">{{ uiText("标签或知识点") }}</option><option value="other">{{ uiText("其他") }}</option></select><textarea v-model="erratumDescription" maxlength="4000" :placeholder="uiText('说明错误内容；如已知，也请写出正确内容。')" /></div>
            <footer><span :class="{ error: erratumMessage && !erratumMessage.startsWith('勘误已提交') }">{{ uiText(erratumMessage) }}</span><button type="button" :disabled="erratumSaving || !erratumDescription.trim()" @click="submitErratum">{{ erratumSaving ? uiText("正在提交…") : uiText("提交勘误") }}</button></footer>
          </section>

          <section v-if="(question.has_answer || question.answer_markdown) && !(question.original_source?.has_answer && question.answer_scope === 'source_paper')" class="official-answer">
            <button class="answer-toggle" :aria-expanded="answerOpen" @click="toggleAnswer">
              <span>{{ answerOpen ? uiText("收起答案") : question.answer_scope === 'individual' ? uiText("查看本题答案与解析") : question.answer_scope === 'source_paper' ? uiText("原卷参考答案（尚未逐题切分）") : question.source_context ? uiText("整卷参考解析（按题号查阅）") : (question.has_answer ? uiText("查看答案") : uiText("查看 Agent 解析")) }}</span><b>{{ answerOpen ? '↑' : '↓' }}</b>
            </button>
            <div v-if="answerOpen" class="answer-canvas">
              <div v-if="question.answer_assets.length" class="asset-toolbar answer-asset-toolbar">
                <button type="button" @click="downloadAssets('answer', question.answer_assets)">{{ uiText("保存答案图片") }}</button>
              </div>
              <template v-for="asset in question.answer_assets" :key="asset.id">
                <img v-show="!failedImages[asset.url]" :src="imageUrl(asset.url)" :width="asset.width" :height="asset.height" :alt="uiText('参考答案')" loading="lazy" decoding="async" @error="markImageFailed(asset.url)" />
                <div v-if="failedImages[asset.url]" class="asset-load-error" role="alert"><span>{{ uiText("答案图片加载失败") }}</span><button type="button" @click="retryImage(asset.url)">{{ uiText("重新加载图片") }}</button></div>
              </template>
              <div v-if="question.answer_markdown" class="agent-answer-block">
                <header><strong>{{ question.answer_source === 'provided-reference' ? uiText("参考答案") : uiText("AGENT 解析") }}</strong><span>{{ question.answer_source || 'agent' }} · {{ question.answer_confidence === null ? uiText("未评级") : `${typeText('置信度', 'Confidence')} ${Math.round(question.answer_confidence * 100)}%` }}</span></header>
                <MarkdownAnswer :source="question.answer_markdown" />
              </div>
            </div>
          </section>
          <p v-if="question.original_source?.has_answer && question.answer_scope === 'source_paper'" class="source-paper-help">{{ uiText("本题答案尚待逐题核对，请先查看完整版答案；不会将未确认的解析错配到本题。") }}</p>
          <OriginalAnswer v-if="question.original_source?.has_answer" :key="question.original_source.uuid + question.uuid" :uuid="question.original_source.uuid" @opened="answerViewedThisRound = true" />
          <p v-else-if="question.original_source && !question.has_answer && !question.answer_markdown" class="source-paper-help">{{ uiText("原始资料未提供参考答案，暂不生成或猜测答案。") }}</p>

          <section v-if="question.source_context" class="source-current-question">
            <strong>{{ uiText("当前记录：") }}{{ question.display_label }}</strong>
            <small>{{ uiText("下方掌握 / 待复习 / 笔记仅保存到这一题。") }}</small>
            <button type="button" @click="sourceViewer?.scrollToCurrent()">{{ uiText("返回本题图中位置 ↗") }}</button>
          </section>
          <section class="answer-workflow">
          <section class="diagnosis-panel">
            <header>
              <div><span>{{ uiText("结构化诊断") }}</span><b class="diagnosis-status" :class="diagnosisSaveState">{{ diagnosisSaveState === 'saving' ? uiText("正在保存…") : diagnosisSaveState === 'saved' ? uiText("已保存 ✓") : diagnosisSaveState === 'error' ? uiText("保存失败") : diagnosisSaveState === 'draft' ? editingAttemptId ? uiText("等待自动保存") : uiText("将随作答保存") : uiText("未填写") }}</b></div>
              <div class="diagnosis-actions"><button type="button" :aria-expanded="historyOpen" @click="loadAttemptHistory">{{ historyOpen ? uiText("收起历史") : uiText("完整历史") }}</button><button type="button" :aria-expanded="diagnosisOpen" @click="diagnosisOpen = !diagnosisOpen">{{ diagnosisOpen ? uiText("收起诊断") : uiText("填写诊断") }}</button></div>
            </header>
            <div v-if="diagnosisOpen" class="diagnosis-body">
            <div class="independence-flags">
              <button type="button" :class="{ active: usedHintThisRound }" @click="toggleUsedHint">{{ usedHintThisRound ? uiText("已使用提示") : uiText("未使用提示") }}</button>
              <span :class="{ compromised: usedHintThisRound || answerViewedThisRound }">{{ usedHintThisRound || answerViewedThisRound ? uiText("本轮不计为独立作答") : uiText("当前可计为独立作答") }}</span>
            </div>
            <button v-if="route.query.mode === 'method'" class="method-note-link" type="button" @click="noteOpen = true">{{ uiText("把调用的知识点和第一个关系式写入“题目笔记”") }}</button>
            <div class="error-picker">
              <button v-for="item in errorOptions" :key="item.code" type="button" :class="{ active: selectedErrors.includes(item.code), primary: primaryError === item.code }" @click="toggleError(item.code)">
                <b>{{ item.code }}</b><span>{{ uiText(item.label) }}</span>
              </button>
            </div>
            <p v-if="selectedErrors.length" class="primary-help">{{ uiText("主要原因：") }}<select v-model="primaryError"><option v-for="code in selectedErrors" :key="code" :value="code">{{ code }} · {{ uiText(errorOptions.find((item) => item.code === code)?.label || '') }}</option></select></p>
            <div class="diagnosis-advanced">
              <label>{{ uiText("知识提取") }}<select v-model="knowledgeLevel"><option :value="null">{{ uiText("未知") }}</option><option value="K0">{{ uiText("K0 不知道") }}</option><option value="K1">{{ uiText("K1 回忆不完整") }}</option><option value="K2">{{ uiText("K2 准确提取") }}</option></select></label>
              <label>{{ uiText("方法启动") }}<select v-model="methodLevel"><option :value="null">{{ uiText("未知") }}</option><option value="M0">{{ uiText("M0 无法开始") }}</option><option value="M1">{{ uiText("M1 需要提示") }}</option><option value="M2">{{ uiText("M2 自主确定路径") }}</option></select></label>
              <label>{{ uiText("执行验证") }}<select v-model="executionLevel"><option :value="null">{{ uiText("未知") }}</option><option value="E0">{{ uiText("E0 无法完成") }}</option><option value="E1">{{ uiText("E1 完成但有误") }}</option><option value="E2">{{ uiText("E2 正确并验证") }}</option></select></label>
            </div>
            <div v-if="historyOpen" class="attempt-history">
              <p v-if="historyLoading">{{ uiText("正在加载历史…") }}</p>
              <p v-else-if="attemptHistory.length">{{ uiText("共") }} {{ attemptHistory.length }} {{ uiText("条作答记录；点击任意记录可查看并自动保存修订。") }}</p>
              <button v-for="attempt in attemptHistory" :key="attempt.id" type="button" @click="editDiagnosis(attempt)"><span><b>{{ uiText("第") }} {{ attempt.attempt_round || '?' }} {{ uiText("轮 ·") }} {{ attempt.training_stage }}</b><small>{{ new Date(attempt.created_at).toLocaleString() }}</small></span><span><b>{{ attempt.outcome }}</b><small>{{ attempt.primary_error || uiText("未诊断") }} · {{ attempt.is_independent === null ? uiText("独立性未知") : attempt.is_independent ? uiText("独立") : uiText("非独立") }}</small></span></button>
              <p v-if="!historyLoading && !attemptHistory.length">{{ uiText("暂无作答记录。") }}</p>
            </div>
            <footer v-if="question.review_plan"><span>{{ uiText("闭环：") }}{{ question.review_plan.checkpoint }}</span><small>{{ question.review_plan.status === 'active' && question.review_plan.next_review_at ? `${typeText('下次', 'Next review')} ${new Date(question.review_plan.next_review_at).toLocaleString()}` : uiText("已完成或暂停") }}</small></footer>
            </div>
          </section>
          <div class="answer-bar">
            <div>
              <div class="question-timer" :class="{ active: !timingCountdown && !timingFinalized, saved: timingFinalized }"><span>{{ timingFinalized ? uiText("计时已保存") : timingCountdown ? uiText("计时准备") : uiText("本题用时") }}</span><strong>{{ timingFinalized || !timingCountdown ? formattedQuestionTime : `${timingCountdown} ${typeText('秒后开始', 'seconds until start')}` }}</strong></div>
              <NoteVisibility :note="note" :question-key="props.uuid">
              <p v-if="note && !noteOpen" class="note-preview" role="button" tabindex="0" @click="noteOpen = true" @keydown.enter="noteOpen = true">{{ note }}</p>
              <details class="note-field" :open="noteOpen" @toggle="toggleNote"><summary><span>{{ uiText("题目笔记 Note") }}</span><small>{{ noteSaveState === 'saving' ? uiText("保存中…") : noteSaveState === 'saved' ? uiText("已保存") : noteSaveState === 'error' ? uiText("保存失败") : noteSaveState === 'dirty' ? uiText("未保存") : note ? uiText("展开编辑") : uiText("添加笔记") }}</small></summary><textarea v-model="note" maxlength="20000" :placeholder="uiText('记录公式、错误原因、修正方法或下次检查点')" @input="cacheNoteDraft" /><span class="note-controls"><small class="note-draft-hint">{{ noteSaveState === 'saving' ? uiText("保存中…") : noteSaveState === 'saved' ? uiText("已保存到服务器") : noteSaveState === 'error' ? uiText("保存失败，本地草稿仍保留") : noteSaveState === 'dirty' ? uiText("未保存") : uiText("停止输入 5 秒后自动保存") }}</small><button type="button" class="save-note" :disabled="noteSaveState === 'saving'" @click="saveNote">{{ noteSaveState === 'saving' ? uiText("保存中…") : noteSaveState === 'error' ? uiText("重试保存") : uiText("保存笔记") }}</button></span></details>
              </NoteVisibility>
            </div>
            <div class="unified-answer-actions"><button class="correct primary-action" :class="{ selected: question.state === 'mastered' }" :disabled="saving" @click="record('correct')">{{ masteredAutoNext ? uiText("掌握并下一题") : uiText("标记已掌握") }}</button><button class="review" :class="{ selected: question.state === 'review' }" :disabled="saving" @click="record('review')">{{ uiText("待复习") }}{{ reviewAutoNext ? uiText("并下一题") : '' }}</button><details class="secondary-actions"><summary>{{ uiText("更多操作") }}</summary><button :disabled="saving || !question.can_undo" @click="undo">{{ uiText("撤销上次") }}</button><button :disabled="saving || question.state === 'unattempted'" @click="record('reset')">{{ uiText("重置本题状态") }}</button></details></div>
          </div>
          </section>


          <button class="similar-trigger" @click="showSimilar"><span>{{ uiText("练习相似题") }}</span><small>{{ uiText("同一已索引知识点") }}</small><b>{{ similarOpen ? '↓' : '→' }}</b></button>
          <section v-if="similarOpen" class="similar-panel">
            <header><span>{{ uiText("相似题组") }}</span><strong>{{ similarTopic || uiText("暂无索引知识点") }}</strong></header>
            <div class="similar-kind-picker">
              <button :class="{ selected: similarKind === 'past_exam' }" :disabled="!similarCounts.past_exam" @click="loadSimilar('past_exam')"><span>{{ uiText("正式历年题") }}</span><strong>{{ similarCounts.past_exam }}</strong><small>{{ uiText("已核验考试来源") }}</small></button>
              <button :class="{ selected: similarKind === 'practice' }" :disabled="!similarCounts.practice" @click="loadSimilar('practice')"><span>{{ uiText("模拟／练习题") }}</span><strong>{{ similarCounts.practice }}</strong><small>{{ uiText("题册、模拟卷和其他练习") }}</small></button>
            </div>
            <p v-if="!similarKind">{{ uiText("请选择要练习的题源类型。") }}</p>
            <p v-else-if="similarLoading">{{ uiText("正在加载相似题…") }}</p>
            <button v-for="item in similar" :key="item.uuid" @click="router.push({ path: `/practice/${item.uuid}`, query: questionRouteQuery() })"><span>{{ item.display_label || `题目 ${item.question_order}` }}</span><small>{{ item.document }} · {{ item.state }} · {{ item.attempt_count }} {{ uiText("次作答") }}</small><b>→</b></button>
            <p v-if="similarKind && !similarLoading && !similar.length">{{ uiText("该知识点下暂无此题源类型的题目。") }}</p>
          </section>

          <section class="page-turn-settings" :aria-label="uiText('翻题偏好')">
            <header><strong>{{ uiText("翻题偏好") }}</strong><label>{{ uiText("前后翻题") }}<select v-model="nextMode"><option value="sequential">{{ uiText("顺序题") }}</option><option value="overdue">{{ uiText("红色到期复习题") }}</option><option value="review">{{ uiText("黄色近期复习题") }}</option></select></label></header>
            <div class="page-turn-settings-grid">
              <label><input v-model="masteredAutoNext" type="checkbox">{{ uiText("掌握后切题") }}</label>
              <label><input v-model="reviewAutoNext" type="checkbox">{{ uiText("待复习后切题") }}</label>
              <label><input v-model="autoCopyLink" type="checkbox">{{ uiText("翻题复制链接") }}</label>
              <label><input v-model="autoCopyImage" type="checkbox">{{ uiText("翻题复制题图") }}</label>
            </div>
            <small>{{ uiText("复制选项二选一；前后翻题均生效。") }}</small>
          </section>
        </aside>
      </div>
    </template>
  </section>
</template>

<style scoped>
.source-current-question { display: grid; gap: 7px; margin-bottom: 10px; padding: 12px; border: 1px solid #3975cb; border-radius: 8px; background: var(--bg-surface); }
.source-current-question strong { font-size: 13px; }
.source-current-question small { font-size: 11px; color: var(--text-secondary); }
.source-current-question button { padding: 7px; border: 1px solid var(--border-default); border-radius: 5px; cursor: pointer; color: var(--text-primary); background: var(--bg-sidebar); }
.source-tracking-toolbar { position: sticky; top: 8px; z-index: 8; display: flex; align-items: center; flex-wrap: wrap; gap: 6px; padding: 8px; border: 1px solid var(--border-default); background: var(--bg-surface); border-radius: 8px; }
.source-tracking-toolbar strong { flex: 1 1 160px; font-size: 12px; color: var(--text-primary); }
.source-tracking-toolbar button { padding: 6px; cursor: pointer; background: var(--bg-sidebar); color: var(--text-primary); border: 1px solid var(--border-default); border-radius: 5px; }
.question-canvas.source-canvas { overflow: visible; }
.source-review-warning { padding: 12px; border: 1px solid #b6872a; border-radius: 8px; color: #b6872a; font-size: 13px; }
.diagnosis-panel { display: grid; gap: 10px; margin-bottom: 12px; padding: 11px 12px; border: 1px solid var(--border-default); border-radius: 10px; background: var(--bg-surface); }
.answer-workflow { overflow: hidden; border: 1px solid var(--border-default); border-radius: 10px; background: var(--bg-surface); display: flex; flex-direction: column; }
.answer-workflow .diagnosis-panel { margin: 0; border: 0; border-bottom: 1px solid var(--border-default); border-radius: 0; }
.answer-workflow .answer-bar { border: 0; border-radius: 0; }
.page-turn-settings { display: grid; gap: 7px; margin-top: 10px; padding: 10px 11px; border: 1px solid var(--border-default); border-radius: 9px; background: var(--bg-surface); }
.page-turn-settings > header { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.page-turn-settings > header strong { color: var(--text-primary); font-size: 12px; }
.page-turn-settings > header label { display: flex; align-items: center; gap: 6px; color: var(--text-secondary); font-size: 10px; white-space: nowrap; }
.page-turn-settings select { max-width: 145px; min-height: 32px; padding: 4px 7px; border: 1px solid var(--border-default); border-radius: 6px; color: var(--text-primary); background: var(--bg-sidebar); font-size: 11px; }
.page-turn-settings-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px; }
.page-turn-settings-grid label { display: flex; align-items: center; gap: 7px; min-width: 0; min-height: 36px; padding: 5px 7px; border: 1px solid var(--border-default); border-radius: 6px; color: var(--text-secondary); background: var(--bg-sidebar); font-size: 11px; line-height: 1.2; cursor: pointer; }
.page-turn-settings-grid label:has(input:checked) { border-color: var(--accent); color: var(--text-primary); background: var(--accent-muted); }
.page-turn-settings-grid input { flex: none; width: 15px; height: 15px; margin: 0; accent-color: var(--accent); }
.page-turn-settings > small { color: var(--text-tertiary); font-size: 10px; line-height: 1.35; }
.diagnosis-status { margin-top: 3px; color: var(--text-tertiary); font-size: 10px; font-weight: 600; }
.diagnosis-status.draft, .diagnosis-status.saving { color: var(--warning); }
.diagnosis-status.saved { color: var(--success); }
.diagnosis-status.error { color: var(--danger); }
.action-feedback { position: fixed; left: 50%; bottom: calc(env(safe-area-inset-bottom) + 18px); z-index: 80; margin: 0; padding: 11px 16px; transform: translateX(-50%); border: 1px solid var(--success); border-radius: 999px; color: #fff; background: color-mix(in srgb, var(--success) 88%, #111); box-shadow: 0 8px 30px rgba(0,0,0,.35); font-size: 12px; font-weight: 750; white-space: nowrap; pointer-events: none; }
.diagnosis-panel > header { display: flex; align-items: start; justify-content: space-between; gap: 10px; }
.diagnosis-panel > header div { display: grid; gap: 3px; }
.diagnosis-panel > header span { font-size: 13px; font-weight: 750; color: var(--text-primary); }
.diagnosis-panel small { color: var(--text-secondary); font-size: 10px; }
.diagnosis-panel button, .diagnosis-panel select, .diagnosis-panel textarea { color: var(--text-primary); background: var(--bg-sidebar); border: 1px solid var(--border-default); border-radius: 7px; }
.diagnosis-panel > header button { padding: 6px 9px; cursor: pointer; white-space: nowrap; }
.diagnosis-actions { display: flex !important; grid-auto-flow: column; gap: 5px; }
.independence-flags { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.independence-flags button { padding: 7px 9px; cursor: pointer; }
.independence-flags button.active { border-color: #d9a928; color: #d9a928; }
.independence-flags span { font-size: 11px; color: #23b66f; }
.independence-flags span.compromised { color: #d9a928; }
.diagnosis-separation-note { margin: 0; padding: 7px 9px; border-left: 3px solid var(--accent); color: var(--text-secondary); background: color-mix(in srgb, var(--accent) 7%, transparent); font-size: 10px; }
.asset-load-error { display: flex; align-items: center; justify-content: center; flex-wrap: wrap; gap: 10px; min-height: 110px; padding: 16px; border: 1px dashed var(--danger); border-radius: 8px; color: var(--danger); background: color-mix(in srgb, var(--danger) 6%, var(--bg-surface)); }
.asset-load-error button { min-height: 40px; padding: 8px 12px; border: 1px solid var(--danger); border-radius: 7px; color: var(--text-primary); background: var(--bg-sidebar); cursor: pointer; }
.method-restart { display: grid; gap: 8px; padding: 10px; border: 1px solid color-mix(in srgb, #d9a928 45%, var(--border-default)); border-radius: 8px; background: color-mix(in srgb, #d9a928 6%, var(--bg-surface)); }
.method-restart label { display: grid; gap: 5px; color: var(--text-secondary); font-size: 11px; }
.method-restart input { min-width: 0; padding: 8px; color: var(--text-primary); background: var(--bg-sidebar); border: 1px solid var(--border-default); border-radius: 6px; }
.error-picker { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px; }
.error-picker button { display: flex; align-items: center; gap: 7px; min-height: 38px; padding: 7px 9px; text-align: left; cursor: pointer; }
.error-picker button b { min-width: 22px; font-size: 11px; }
.error-picker button span { font-size: 11px; }
.error-picker button.active { border-color: #d9a928; background: color-mix(in srgb, #d9a928 10%, var(--bg-surface)); }
.error-picker button.primary { box-shadow: inset 3px 0 #d9a928; }
.primary-help { margin: 0; font-size: 11px; color: var(--text-secondary); }
.primary-help select { margin-left: 5px; padding: 5px; }
.diagnosis-advanced { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 7px; }
.diagnosis-advanced label { display: grid; gap: 5px; font-size: 10px; color: var(--text-secondary); }
.diagnosis-advanced select { min-width: 0; padding: 7px 5px; }
.diagnosis-advanced .correction-field { grid-column: 1 / -1; }
.diagnosis-advanced textarea { min-height: 72px; padding: 8px; resize: vertical; }
.diagnosis-panel > footer { display: flex; justify-content: space-between; gap: 8px; padding-top: 8px; border-top: 1px solid var(--border-default); font-size: 11px; }
.save-diagnosis-edit { padding: 9px; border-color: #d9a928 !important; cursor: pointer; }
.attempt-history { display: grid; gap: 5px; padding-top: 8px; border-top: 1px solid var(--border-default); }
.attempt-history > button { display: grid; grid-template-columns: 1fr auto; gap: 8px; padding: 8px; text-align: left; cursor: pointer; }
.attempt-history > button span { display: grid; gap: 3px; }
.attempt-history > button span:last-child { text-align: right; }
.attempt-history p { margin: 4px 0; color: var(--text-secondary); font-size: 10px; }
@media (max-width: 720px) { .diagnosis-advanced { grid-template-columns: 1fr; } .diagnosis-advanced .correction-field { grid-column: auto; } }
@media (max-width: 900px) { .action-feedback { bottom: calc(env(safe-area-inset-bottom) + 78px); max-width: calc(100vw - 24px); white-space: normal; text-align: center; } }
/* Compact diagnosis: two rows of error codes, without changing selection or autosave. */
.diagnosis-panel { gap: 5px; padding: 6px; }
.diagnosis-panel > header { align-items: center; gap: 5px; }
.diagnosis-panel > header > div:first-child { display: flex; flex-wrap: wrap; align-items: center; gap: 3px 6px; min-width: 0; }
.diagnosis-panel > header span { font-size: 11px; line-height: 1.2; }
.diagnosis-status { margin-top: 0; font-size: 9px; }
.diagnosis-panel > header button { min-height: 28px; padding: 3px 5px; font-size: 10px; border-radius: 5px; }
.diagnosis-actions { flex-shrink: 0; gap: 3px; }
.diagnosis-body { gap: 5px; }
.independence-flags { gap: 4px; }
.independence-flags button { min-height: 28px; padding: 3px 5px; font-size: 10px; }
.independence-flags span { font-size: 10px; line-height: 1.25; }
.error-picker { grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 4px; }
.error-picker button { min-width: 0; min-height: 40px; padding: 3px 2px; gap: 2px; flex-direction: column; justify-content: center; text-align: center; border-radius: 5px; }
.error-picker button b { min-width: 0; font-size: 10px; line-height: 1.1; }
.error-picker button span { font-size: 10px; line-height: 1.15; overflow-wrap: anywhere; }
.diagnosis-advanced { grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 4px; }
.diagnosis-advanced label { min-width: 0; gap: 2px; font-size: 9px; }
.diagnosis-advanced select { width: 100%; min-height: 28px; padding: 3px 1px; font-size: 10px; }
.primary-help { font-size: 10px; }
.primary-help select { max-width: 75%; min-height: 28px; padding: 2px; }
.diagnosis-body > footer { display: flex; flex-wrap: wrap; gap: 4px; font-size: 10px; }
</style>
