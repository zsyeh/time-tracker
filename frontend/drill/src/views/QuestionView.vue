<script setup lang="ts">
import { uiText } from '../lib/uiText'
import { ForegroundTimer, learningUserId, readLocal, writeLocal, type TimingSyncResult } from '../../../shared/foregroundTimer'
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import { api, ApiError, post, remove } from '../lib/api'
import { cachedNoteDraft, cachedQuestion, clearNoteDraft, fetchNavigationQuestion, fetchQuestion, patchQuestionState, prefetchQuestion, storeNoteDraft, warmQuestionMedia } from '../lib/workspace'
import type { AttemptDiagnosis, ErrorCode, QuestionDetail, QuestionSummary } from '../types'
import ExamTypeEditor from '../components/ExamTypeEditor.vue'
import NoteVisibility from '../components/NoteVisibility.vue'
import DiagnosisSelector from '../components/DiagnosisSelector.vue'
import PracticeActionToolbar from '../components/PracticeActionToolbar.vue'
import { typeText } from '../lib/examTypes'
import type { ReaderPracticeAction, ReaderPracticeControls } from '../lib/readerPractice'
import MarkdownAnswer from '../components/MarkdownAnswer.vue'
import SourcePaperViewer from '../components/SourcePaperViewer.vue'
import OriginalAnswer from '../components/OriginalAnswer.vue'
import FullscreenReader from '../components/FullscreenReader.vue'
import { sourcePracticeTarget } from '../lib/sourcePractice'
import { circuitFilters } from '../lib/circuitSelected'
import { createAndCopyShare, createAndCopyShareOnGesture } from '../lib/share'
import { notifyPracticeTrendChanged } from '../lib/practiceTrend'
import { emptyNextQuestionMessage, emptyPreviousQuestionMessage, nextQuestionTarget, previousQuestionTarget, type NextQuestionMode } from '../lib/questionNavigation'
import { runtimeWorkspace, withWorkspacePrefix } from '../lib/runtimePath'
import { buildClipboardPng, copyImagesToClipboard, downloadImageBlob, shareImageBlob } from '../lib/imageClipboard'
import { useUiPreferences } from '../lib/uiPreferences'
import { usePracticePreferences } from '../lib/practicePreferences'

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
  return Object.fromEntries(['type_group', 'exam_type', 'document', 'topic', 'source_category', 'q', 'unattempted', 'marker', 'collection', 'bucket', 'tier', 'kind', 'material', 'combined', 'state', 'scope', 'course', 'mode', 'sort', 'search_version', 'index_version', 'status', 'favorite', 'review_later', 'practice_page', 'insight_return', 'insight_list', 'collection_page', 'from']
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
  const query = navigationQuery()
  if (query.practice_page) query.page = query.practice_page
  delete query.practice_page
  void router.push({ path: '/practice', query })
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
  sequential: '上一题', overdue: '上一道红色题', review: '上一道黄色题', unattempted: '上一道未做题',
})[nextMode.value])
const topNextLabel = computed(() => question.value ? ({
  sequential: '下一题', overdue: '下一道到期题', review: '下一道待复习题', unattempted: '下一道未做题',
})[nextMode.value] : '下一题')
const sourceViewer = ref<InstanceType<typeof SourcePaperViewer> | null>(null)
const questionReader = ref<InstanceType<typeof FullscreenReader> | null>(null)
const originalAnswerReader = ref<InstanceType<typeof OriginalAnswer> | null>(null)
const pendingFullscreenTarget = ref<string | null>(null)
type ReaderKind = 'question' | 'answer' | 'original'
const readerKind = ref<ReaderKind>('question')
const readerNavigating = ref(false)
const readerPreparing = ref(false)
const rejectedReaderCache = new Set<string>()
let readerSequence = 0
const readerDocument = ref<{ uuid: string; key: string; title: string; images: Array<{ src: string; width: number; height: number }>; markdown: string }>({ uuid: '', key: '', title: '', images: [], markdown: '' })
function isReaderOpen() { return Boolean(questionReader.value?.isOpen) }
function showReaderDocument(value: QuestionDetail, kind: ReaderKind = 'question', original?: QuestionDetail) {
  readerKind.value = kind
  const source = original || value
  const assets = kind === 'question' ? questionAssets(source) : source.answer_assets
  readerDocument.value = {
    uuid: value.uuid, key: `${value.uuid}:${kind}`,
    title: (kind === 'question' ? typeText('题目', 'Question') : kind === 'original' ? typeText('完整答案', 'Complete answers') : typeText('答案', 'Answer')) + ' · ' + value.display_label,
    images: assets.map(asset => ({ src: imageUrl(asset.url), width: asset.width, height: asset.height })),
    markdown: kind === 'question' ? (!assets.length ? source.prompt_text : '') : source.answer_markdown || '',
  }
}
async function prepareReader() {
  if (readerKind.value !== 'original') return
  const sequence = readerSequence
  const current = question.value
  const source = originalAnswerReader.value
  if (!current || !source) return
  readerPreparing.value = true
  try {
    const original = await source.readFullscreenAnswer()
    if (sequence === readerSequence && question.value?.uuid === current.uuid) showReaderDocument(current, 'original', original)
  } finally { if (sequence === readerSequence) readerPreparing.value = false }
}
async function openReader(kind: ReaderKind) {
  if (!question.value) return
  readerSequence += 1
  const current = question.value
  if (kind === 'original') {
    readerKind.value = kind
    readerDocument.value = { uuid: current.uuid, key: `${current.uuid}:original`, title: typeText('完整答案', 'Complete answers') + ' · ' + current.display_label, images: [], markdown: '' }
  } else showReaderDocument(current, kind)
  if (kind !== 'question') answerViewedThisRound.value = true
  await nextTick()
  await questionReader.value?.open()
}
function readerClosed() {
  readerSequence += 1
  readerPreparing.value = false
  readerNavigating.value = false
  pendingFullscreenTarget.value = null
}
async function readerAction(action: ReaderPracticeAction) {
  if (readerControls.value.busy) return
  if (action === 'previous') goToPrevious()
  else if (action === 'next') await goToNext(nextMode.value)
  else if (action === 'mastered') await record('correct')
  else if (action === 'review') await record('review')
  else if (action === 'answer') {
    if (readerKind.value !== 'question') {
      await openReader('question')
      return
    }
    const original = question.value?.original_source?.has_answer && (question.value.answer_scope === 'source_paper' || (!question.value.has_answer && !question.value.answer_markdown))
    await openReader(original ? 'original' : 'answer')
  }
}

function navigateToQuestion(uuid: string | null, direction: 'previous' | 'next', copyArmed = false) {
  if (!uuid) return
  pendingFullscreenTarget.value = isReaderOpen() ? uuid : null
  if (pendingFullscreenTarget.value) {
    readerSequence += 1
    readerNavigating.value = true
    readerKind.value = 'question'
    readerDocument.value = { uuid: '', key: `loading:${uuid}`, title: typeText('正在加载题目…', 'Loading question…'), images: [], markdown: '' }
  }
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
  return router.push({ path: `/practice/${uuid}`, query: questionRouteQuery() })
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
const { nextMode, pageTurnCopyMode, reviewAutoNext, masteredAutoNext } = usePracticePreferences()
const autoCopyLink = computed({
  get: () => pageTurnCopyMode.value === 'link',
  set: (enabled: boolean) => { pageTurnCopyMode.value = enabled ? 'link' : 'off' },
})
const autoCopyImage = computed({
  get: () => pageTurnCopyMode.value === 'image',
  set: (enabled: boolean) => { pageTurnCopyMode.value = enabled ? 'image' : 'off' },
})
const readerControls = computed<ReaderPracticeControls>(() => ({
  mode: nextMode.value,
  canPrevious: Boolean(topPreviousTarget.value), canNext: Boolean(topNextTarget.value),
  answerActive: readerKind.value !== 'question',
  canAnswer: Boolean(question.value?.has_answer || question.value?.answer_markdown || question.value?.original_source?.has_answer),
  busy: saving.value || nextLoading.value || loading.value || readerNavigating.value || readerPreparing.value || !question.value,
  masteredAutoNext: masteredAutoNext.value, reviewAutoNext: reviewAutoNext.value,
  state: question.value?.state || 'unattempted', error: uiText(error.value), feedback: uiText(actionFeedback.value),
}))

watch(nextMode, (value) => {
  if(value==='unattempted'&&question.value){
    const query=navigationQueryString()
    void prefetchQuestion(question.value.next_unattempted_question_uuid||null,query)
    void prefetchQuestion(question.value.previous_unattempted_question_uuid||null,query)
  }
})
watch(diagnosisOpen, (value) => localStorage.setItem(`${runtimeWorkspace}.diagnosis-open.v1`, String(value)))

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
let questionTimerInterval = 0
let practiceTimer: ForegroundTimer | null = null
let roundDraftReady = false
let draftRoundKey = ''
const timerSyncStatus = ref('syncing')
const timingRecoveryResult = ref<'correct'|'review'|'reset'|null>(null)
const pendingAttemptResult = ref<'correct'|'review'|'reset'|null>(null)
const timerReconnecting = ref(false)
const timingIssueReason = ref('')
const timingCountdown = ref(5)
const timingElapsedSeconds = ref(0)
const timingFinalized = ref(false)
const timingOmitted = ref(false)
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
  practiceTimer?.tick()
}
function renderTimer() {
  if (!practiceTimer) return
  if (roundDraftReady && draftRoundKey !== practiceTimer.state.key) restoreRoundDraft()
  timingCountdown.value = Math.ceil(practiceTimer.state.countdownMs / 1000)
  timingElapsedSeconds.value = Math.ceil(practiceTimer.state.elapsedMs / 1000)
  timingFinalized.value = practiceTimer.state.finalized
  timerSyncStatus.value = practiceTimer.status
  timingIssueReason.value = practiceTimer.issue?.reason || ''
  const pendingResult = practiceTimer.state.pendingAttempt?.result
  pendingAttemptResult.value = pendingResult === 'correct' || pendingResult === 'review' || pendingResult === 'reset' ? pendingResult : null
}
function resetQuestionTimer() {
  timingOmitted.value=false
  window.clearInterval(questionTimerInterval)
  if (practiceTimer) void practiceTimer.dispose()
  roundDraftReady = false
  practiceTimer = new ForegroundTimer(learningUserId, runtimeWorkspace, props.uuid, api, renderTimer)
  renderTimer()
  questionTimerInterval = window.setInterval(updateQuestionTimer, 500)
}
function syncQuestionTimer(uuid: string) {
  if (practiceTimer?.uuid === uuid) return practiceTimer.activate()
  return Promise.resolve()
}
function persistRoundDraft() {
  if (!practiceTimer || !roundDraftReady || draftRoundKey !== practiceTimer.state.key || diagnosisHydrating || editingAttemptId.value || practiceTimer.state.finalized) return
  writeLocal(practiceTimer.storageKey + '.draft', { key: practiceTimer.state.key,
    knowledge: knowledgeLevel.value, method: methodLevel.value, execution: executionLevel.value,
    errors: selectedErrors.value, primary: primaryError.value,
    hint: usedHintThisRound.value, answer: answerViewedThisRound.value })
}
function restoreRoundDraft() {
  if (!practiceTimer) return
  const d = readLocal<{key: string; knowledge: typeof knowledgeLevel.value; method: typeof methodLevel.value;
    execution: typeof executionLevel.value; errors: typeof selectedErrors.value; primary: typeof primaryError.value; hint: boolean; answer: boolean; pending_edits?: boolean}>(practiceTimer.storageKey + '.draft')
  const valid = d?.key === practiceTimer.state.key || d?.pending_edits === true ? d : null
  diagnosisHydrating = true
  knowledgeLevel.value = valid?.knowledge ?? null; methodLevel.value = valid?.method ?? null; executionLevel.value = valid?.execution ?? null
  selectedErrors.value = valid?.errors || []; primaryError.value = valid?.primary ?? null
  usedHintThisRound.value = valid?.hint === true; answerViewedThisRound.value = valid?.answer === true
  diagnosisHydrating = false
  draftRoundKey = practiceTimer.state.key
  roundDraftReady = true
  if(d?.pending_edits)persistRoundDraft()
}
watch([knowledgeLevel, methodLevel, executionLevel, selectedErrors, primaryError, usedHintThisRound, answerViewedThisRound], persistRoundDraft, { deep: true, flush: 'sync' })
function persistLearningBoundary() {
  flushNoteDraft(); persistRoundDraft()
  void practiceTimer?.pause()
}
function learningVisibility() {
  if (document.visibilityState === 'hidden') persistLearningBoundary()
  else void practiceTimer?.activate()
}
function learningOnline() { void practiceTimer?.activate() }

function timerFailureMessage(sync: TimingSyncResult) {
  if(sync.status==='success')return ''
  return sync.issue.reason==='owner_mismatch'||sync.issue.reason==='ownership_conflict'
    ? typeText('另一学习窗口仍在使用计时。请先暂停该窗口，再重新连接；也可明确选择不记录本次用时保存作答。','Another study window owns the timer. Pause it and reconnect, or explicitly save this answer without duration.')
    : typeText('计时尚未连接，作答未提交；本地笔记、诊断和计时仍保留。请重新连接，或选择不记录本次用时保存。','Timing is not connected; the answer was not submitted. Notes, diagnosis and local timing are retained. Reconnect, or save without duration.')
}
async function reconnectQuestionTimer() {
  if(timerReconnecting.value||saving.value||!practiceTimer)return
  const timer=practiceTimer
  timerReconnecting.value=true
  try{
    // Preserve the visible form even when the server has already finalized the
    // old round; reconnect may create a new key without changing these choices.
    writeLocal(timer.storageKey+'.draft',{key:timer.state.key,knowledge:knowledgeLevel.value,method:methodLevel.value,
      execution:executionLevel.value,errors:selectedErrors.value,primary:primaryError.value,hint:usedHintThisRound.value,answer:answerViewedThisRound.value})
    const result=await timer.reconnect()
    if(practiceTimer!==timer)return
    error.value=timerFailureMessage(result)
    if(result.status==='success'){
      timingRecoveryResult.value=null
      if(timer.state.pendingAttempt)error.value=typeText('上次作答尚待确认，请点击“重试上次作答”；不会重复计入。','The previous submission still needs confirmation. Retry it; it will not be counted twice.')
    }
  }finally{timerReconnecting.value=false}
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

function persistNoteDraft(uuid: string, value: string) {
  const persisted = storeNoteDraft(uuid, value)
  if (!persisted && props.uuid === uuid) {
    noteSaveState.value = 'error'
    error.value = typeText('浏览器无法保存笔记草稿；请保存到服务器，关闭页面可能丢失未保存内容。', 'Browser could not persist the note draft. Save it to the server before closing this page.')
  }
  return persisted
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
    noteDraftDirty = !persistNoteDraft(uuid, value)
  }, 300)
  noteAutoSaveTimer = window.setTimeout(() => {
    if (props.uuid === uuid && note.value === value) void saveNote()
  }, 5000)
}

function flushNoteDraft(uuid = props.uuid) {
  if (!noteDraftDirty) return
  window.clearTimeout(noteDraftTimer)
  noteDraftDirty = !persistNoteDraft(uuid, note.value)
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
  if (nextMode.value === 'unattempted') {
    void prefetchQuestion(loadedQuestion.next_unattempted_question_uuid ?? null, query)
    void prefetchQuestion(loadedQuestion.previous_unattempted_question_uuid ?? null, query)
  }
}

async function load() {
  loadController?.abort()
  loadController = new AbortController()
  const controller = loadController
  const sequence = ++loadSequence
  const uuid = props.uuid
  const query = navigationQueryString()
  const cached = rejectedReaderCache.has(uuid) ? null : cachedQuestion(props.uuid, query)
  if (pendingFullscreenTarget.value === uuid) readerNavigating.value = true
  loading.value = !cached
  if (cached) useQuestion(cached)
  else question.value = null
  error.value = ''
  errorStatus.value = null
  similarOpen.value = false
  diagnosisHydrating = true
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
  pendingSubmissionKey.value = practiceTimer?.state.submissionKey || null
  historyOpen.value = false
  attemptHistory.value = []
  editingAttemptId.value = null
  similar.value = []
  similarTopic.value = ''
  similarKind.value = ''
  restoreRoundDraft()
  similarCounts.value = { past_exam: 0, practice: 0 }
  try {
    const direct = pendingFullscreenTarget.value === uuid
    const request = direct ? fetchNavigationQuestion(uuid, query, controller.signal) : fetchQuestion(uuid, query, Boolean(cached), controller.signal)
    void request.catch(() => { /* The awaited request below handles errors, including aborted navigation. */ })
    if (direct && cached) {
      showReaderDocument(cached)
      await nextTick()
      if (sequence === loadSequence && pendingFullscreenTarget.value === uuid && !isReaderOpen()) await questionReader.value?.open()
    }
    const loadedQuestion = await request
    if (sequence !== loadSequence) return
    const individualUuid = sourcePracticeTarget(loadedQuestion, route.query.view)
    if (individualUuid) {
      if (pendingFullscreenTarget.value === uuid) pendingFullscreenTarget.value = individualUuid
      await router.replace({ path: `/practice/${individualUuid}`, query: questionRouteQuery() })
      return
    }
    rejectedReaderCache.delete(uuid)
    useQuestion(loadedQuestion)
    restoreRoundDraft()
    if (pendingFullscreenTarget.value === uuid) showReaderDocument(loadedQuestion)
    else if (isReaderOpen() && readerDocument.value.uuid === uuid && readerKind.value !== 'original') showReaderDocument(loadedQuestion, readerKind.value)
    schedulePrefetch(loadedQuestion)
  } catch (reason) {
    if (sequence !== loadSequence || (reason as Error).name === 'AbortError') return
    error.value = (reason as Error).message
    errorStatus.value = reason instanceof ApiError ? reason.status : 0
    if (sequence === loadSequence) {
      rejectedReaderCache.add(uuid)
      question.value = null
      if (pendingFullscreenTarget.value === uuid || (isReaderOpen() && readerDocument.value.uuid === uuid)) {
        readerDocument.value = { uuid: '', key: `error:${uuid}`, title: typeText('题目暂不可用', 'Question unavailable'), images: [], markdown: '' }
      }
    }
  } finally {
    if (sequence === loadSequence) {
      loading.value = false
      readerNavigating.value = false
      if (loadController === controller) loadController = null
      await nextTick()
      if (question.value?.uuid === uuid && pendingFullscreenTarget.value === uuid && props.uuid === uuid) {
        pendingFullscreenTarget.value = null
        if (!isReaderOpen()) await questionReader.value?.open()
      }
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
  // Render the authoritative response before optional cache/invalidation work.
  if (props.uuid === uuid && question.value?.uuid === uuid) {
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
  try { patchQuestionState(uuid, response) } catch { /* cache cannot undo server state */ }
}
async function record(result: 'correct' | 'review' | 'reset', omitTiming = false) {
  if (saving.value || !question.value) return
  window.clearTimeout(diagnosisSaveTimer)
  diagnosisSaveSequence += 1
  const uuid = props.uuid
  const roundTimer = practiceTimer
  const sequence = ++operationSequence
  saving.value = true
  const submittedNote = note.value
  const willTurn = (result === 'correct' && masteredAutoNext.value)
    || (result === 'review' && reviewAutoNext.value)
  let pendingCopy: { resolve: (uuid: string) => void; reject: (reason: Error) => void } | null = null
  let copyArmed = false
  let attemptSaved = false
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
    const pendingBody=roundTimer?.state.pendingAttempt
    if(pendingBody&&pendingBody.result!==result){
      error.value=typeText('上次作答结果尚未确认，请先点击“重试上次作答”。','The previous answer is not confirmed. Retry the previous submission first.')
      return
    }
    if(!pendingBody&&!omitTiming&&roundTimer){
      const ready=await roundTimer.prepareSubmission()
      if(props.uuid!==uuid||sequence!==operationSequence)return
      if(ready.status!=='success'||(ready.finalized&&!pendingSubmissionKey.value&&!roundTimer.state.submissionKey)){
        timingRecoveryResult.value=result
        error.value=ready.status==='success'?typeText('本轮计时已结束，请重新连接或选择不记录本次用时保存。','This timing round has ended. Reconnect or save without duration.'):timerFailureMessage(ready)
        return
      }
    }
    if(props.uuid!==uuid||sequence!==operationSequence)return
    const timingSnapshot=pendingBody||roundTimer?.snapshot()||{}
    const timeSpentSeconds=!omitTiming&&(result==='correct'||result==='review')?recordedQuestionSeconds():null
    if(!pendingSubmissionKey.value)pendingSubmissionKey.value=String(pendingBody?.submission_key||roundTimer?.submissionKey()||crypto.randomUUID())
    const body:Record<string,unknown>=pendingBody?{...pendingBody}:{
      result,
      note: note.value,
      state_version: question.value?.state_version || undefined,
      ...timingSnapshot,
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
    }
    if(omitTiming){
      if(!pendingBody&&(roundTimer?.state.finalized||roundTimer?.issue?.reason==='timing_finalized'))body.timing_key=crypto.randomUUID()
      body.timing_protocol=2;body.timing_omit=true
      delete body.time_spent_seconds
      delete body.started_at
    }
    const diagnosisBaseline=pendingBody||{knowledge_level:knowledgeLevel.value,method_level:methodLevel.value,execution_level:executionLevel.value,
      used_hint:usedHintThisRound.value,viewed_answer:answerViewedThisRound.value,error_codes:[...selectedErrors.value],primary_error:primaryError.value}
    roundTimer?.rememberAttempt(body)
    const response=await post<StateResponse>(`/api/drill/questions/${uuid}/attempts/`,body)
    // The POST is the commit boundary; cache, refresh and navigation are optional
    // follow-up work and must never turn this acknowledged attempt into a failure.
    attemptSaved = true
    const noteToPreserve=props.uuid===uuid&&note.value!==String(body.note??'')?note.value:null
    const newerDiagnosis=props.uuid===uuid&&(result==='correct'||result==='review')&&(
      knowledgeLevel.value!==diagnosisBaseline.knowledge_level||methodLevel.value!==diagnosisBaseline.method_level||executionLevel.value!==diagnosisBaseline.execution_level||
      usedHintThisRound.value!==diagnosisBaseline.used_hint||answerViewedThisRound.value!==diagnosisBaseline.viewed_answer||
      JSON.stringify(selectedErrors.value)!==JSON.stringify(diagnosisBaseline.error_codes||[])||primaryError.value!==diagnosisBaseline.primary_error)
    if(newerDiagnosis&&roundTimer)writeLocal(roundTimer.storageKey+'.draft',{key:roundTimer.state.key,pending_edits:true,
      knowledge:knowledgeLevel.value,method:methodLevel.value,execution:executionLevel.value,errors:selectedErrors.value,primary:primaryError.value,
      hint:usedHintThisRound.value,answer:answerViewedThisRound.value})
    if(omitTiming)roundTimer?.archiveOmittedRound()
    roundTimer?.finish()
    if (sequence !== operationSequence) return
    timingRecoveryResult.value=null
    timingOmitted.value=omitTiming&&response.last_time_spent_seconds==null
    if (result === 'correct' || result === 'review') {
      timingFinalized.value = true
      window.clearInterval(questionTimerInterval)
    }
    pendingSubmissionKey.value = null
    if (!response.note_conflict&&noteToPreserve===null) discardNoteDraft(uuid)
    applyState(response, uuid)
    try { notifyPracticeTrendChanged() } catch { /* statistics refresh cannot undo a saved attempt */ }
    if (props.uuid !== uuid) return
    editingAttemptId.value = null
    diagnosisSaveState.value = result === 'correct' || result === 'review' ? 'saved' : 'idle'
    if (result === 'correct' || result === 'review') {
      window.clearTimeout(actionFeedbackTimer)
      actionFeedback.value = result === 'correct' ? '已保存：掌握状态与本轮诊断' : '已保存：待复习状态与本轮诊断'
      actionFeedbackTimer = window.setTimeout(() => { actionFeedback.value = '' }, 1800)
    }
    noteSaveState.value = response.note_conflict ? 'error' : 'idle'
    if(noteToPreserve!==null){note.value=noteToPreserve;cacheNoteDraft()}
    if(noteToPreserve!==null||newerDiagnosis){
      error.value=typeText('上次作答已确认；之后编辑的笔记或诊断仍保留为草稿，尚未包含在该次作答中。','Previous answer confirmed. Later note or diagnosis edits are retained as drafts and were not included in that submission.')
    }
    if (response.note_conflict) {
      note.value = noteToPreserve??submittedNote
      const draftPersisted = persistNoteDraft(uuid, note.value)
      if (draftPersisted) error.value = '作答已保存，但笔记在另一标签页被更新；本地草稿已保留，请确认后再保存。'
    }
    if (result === 'reset') {
      resetQuestionTimer()
      if (practiceTimer) { draftRoundKey = practiceTimer.state.key; roundDraftReady = true; persistRoundDraft() }
      void syncQuestionTimer(props.uuid)
    }
    if (willTurn) {
      const target = question.value ? nextQuestionTarget(question.value, nextMode.value) : null
      if (target) pendingCopy?.resolve(target)
      else pendingCopy?.reject(new Error(emptyNextQuestionMessage(nextMode.value)))
      pendingCopy = null
      await goToNext(nextMode.value, copyArmed)
    }
  } catch (reason) {
    if (!attemptSaved) {
      if(reason instanceof ApiError&&reason.status>=400&&reason.status<500){
        roundTimer?.clearPreparedAttempt()
        if(reason.status===409&&typeof reason.body.reason==='string'){
          timingRecoveryResult.value=result
          roundTimer?.recordFailure(reason)
        }
      }
      roundTimer?.resumeAfterFailure()
    }
    if (props.uuid === uuid && sequence === operationSequence) {
      error.value = attemptSaved
        ? typeText(`作答已保存，后续操作未完成：${(reason as Error).message}`, `Answer saved; follow-up action failed: ${(reason as Error).message}`)
        : timingRecoveryResult.value&&roundTimer?.issue?timerFailureMessage({status:'conflict',issue:roundTimer.issue}):(reason as Error).message
    }
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
    persistNoteDraft(uuid, value)
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
  void navigateToQuestion(target, 'previous')?.catch((reason: Error) => { error.value = reason.message; readerNavigating.value = false })
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
    await navigateToQuestion(target, 'next', copyArmed)
  } catch (reason) {
    readerNavigating.value = false
    if (props.uuid === uuid) error.value = `无法进入下一题：${(reason as Error).message}`
  } finally {
    if (props.uuid === uuid) nextLoading.value = false
  }
}

watch(() => props.uuid, (_uuid, previousUuid) => {
  loadController?.abort()
  operationSequence += 1
  saving.value = false
  timingRecoveryResult.value=null
  pendingAttemptResult.value=null
  stateSaving.value = false
  similarLoading.value = false
  nextLoading.value = false
  window.clearTimeout(diagnosisSaveTimer)
  diagnosisSaveSequence += 1
  diagnosisSaveState.value = 'idle'
  window.clearTimeout(noteAutoSaveTimer)
  window.clearTimeout(noteSavedTimer)
  persistRoundDraft()
  flushNoteDraft(previousUuid)
  noteSaveState.value = 'idle'
  resetQuestionTimer()
  void syncQuestionTimer(_uuid)
  void load()
})

function refreshAfterPageRestore(event: PageTransitionEvent) {
  if (!event.persisted) return
  operationSequence += 1
  void practiceTimer?.activate()
  void load()
}

onMounted(() => {
  window.addEventListener('pageshow', refreshAfterPageRestore)
  document.addEventListener('visibilitychange', learningVisibility)
  window.addEventListener('pagehide', persistLearningBoundary)
  window.addEventListener('online', learningOnline)
  resetQuestionTimer()
  void syncQuestionTimer(props.uuid)
  void load()
})
onUnmounted(() => {
  window.removeEventListener('pageshow', refreshAfterPageRestore)
  document.removeEventListener('visibilitychange', learningVisibility)
  window.removeEventListener('pagehide', persistLearningBoundary)
  window.removeEventListener('online', learningOnline)
  persistRoundDraft()
  void practiceTimer?.dispose()
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
  if (String(to.params.uuid || '') !== props.uuid) { flushNoteDraft(); persistRoundDraft() }
})
onBeforeRouteLeave(() => {
  flushNoteDraft(); persistRoundDraft()
})
</script>

<template>
  <section class="page question-page">
    <FullscreenReader ref="questionReader" hide-trigger :controls="readerControls" :content-key="readerDocument.key" :title="readerDocument.title" :images="readerDocument.images" :markdown="readerDocument.markdown" :prepare="prepareReader" :pending="readerNavigating && readerDocument.uuid !== props.uuid" :syncing="readerNavigating && readerDocument.uuid === props.uuid" :retryable="!question && !!error && pendingFullscreenTarget === props.uuid" @retry="load" @action="readerAction" @closed="readerClosed">
      <template #recovery>
        <div v-if="timerSyncStatus==='offline'||timerSyncStatus==='conflict'||timingRecoveryResult||pendingAttemptResult" class="timing-recovery in-reader" role="status">
                <button type="button" :disabled="saving||timerReconnecting" @click="reconnectQuestionTimer">{{ timerReconnecting?typeText('连接中…','Connecting…'):typeText('重新连接计时','Reconnect timer') }}</button>
                <button v-if="pendingAttemptResult" type="button" :disabled="saving" @click="record(pendingAttemptResult)">{{ typeText('重试上次作答','Retry previous submission') }}</button>
                <button v-if="timingRecoveryResult" type="button" :disabled="saving||timerReconnecting" @click="record(timingRecoveryResult,true)">{{ typeText('不记录本次用时，保存作答','Save answer without duration') }}</button>
                <small v-if="timingIssueReason">{{ typeText('计时状态','Timing status') }}: {{ timingIssueReason }}</small>
              </div>
      </template>
    </FullscreenReader>
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
        <button type="button" :aria-pressed="question.is_favorite" :class="{ active: question.is_favorite }" :disabled="stateSaving" @click="saveUserState({ is_favorite: !question.is_favorite })"><b>{{ question.is_favorite ? '★' : '☆' }}</b>{{ question.is_favorite ? uiText("已收藏") : uiText("收藏") }}</button>
        <button type="button" :disabled="shareState === 'sharing'" @click="shareQuestion"><b>↗</b>{{ shareState === 'sharing' ? uiText("正在生成…") : shareState === 'copied' ? uiText("链接已复制 ✓") : uiText("复制分享链接") }}</button>
        <button type="button" :aria-pressed="question.review_later" :class="{ active: question.review_later }" :disabled="stateSaving" @click="saveUserState({ review_later: !question.review_later })"><b>↻</b>{{ question.review_later ? uiText("已加入下次复习") : uiText("加入下次复习") }}</button>
        <button type="button" :aria-expanded="erratumOpen" :class="{ active: erratumOpen }" @click="erratumOpen = !erratumOpen"><b>!</b>{{ uiText("提交勘误") }}</button>
      </div>

      <div class="question-workbench">
        <div class="question-problem-pane">
          <p v-if="question.source_review_warning" role="note" class="source-review-warning">{{ question.source_review_warning }}</p>
          <p v-if="question.original_source" class="source-original-link"><RouterLink :to="{ path: `/practice/${question.original_source.uuid}`, query: { ...questionRouteQuery(), view: 'original' } }">{{ uiText("查看完整原卷／原页（原始题图已保留） ↗") }}</RouterLink></p>
          <nav v-if="question.source_context" class="source-tracking-toolbar" :aria-label="uiText('当前小题掌握情况')">
            <strong>{{ question.display_label }}</strong>
            <button @click="sourceViewer?.scrollToCurrent()">{{ uiText("定位本题") }}</button>
          </nav>
          <div class="asset-toolbar question-asset-toolbar">
            <button type="button" class="fullscreen-trigger inline-fullscreen-trigger" :title="typeText('题目全屏', 'Question full screen')" :aria-label="typeText('题目全屏', 'Question full screen')" @click="openReader('question')"><svg width="15" height="15" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M7 3H3v4m10-4h4v4M3 13v4h4m10-4v4h-4" /></svg></button>
            <button v-if="questionAssets(question).length" class="copy-question-image" type="button" :disabled="imageCopyState === 'copying'" @click="copyQuestionImages">{{ imageCopyState === 'copying' ? uiText("正在复制…") : imageCopyState === 'copied' ? uiText("已复制题图 ✓") : uiText("复制题图") }}</button>
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
            <div class="answer-heading">
            <button class="answer-toggle" :aria-expanded="answerOpen" @click="toggleAnswer">
              <span>{{ answerOpen ? uiText("收起答案") : question.answer_scope === 'individual' ? uiText("查看本题答案与解析") : question.answer_scope === 'source_paper' ? uiText("原卷参考答案（尚未逐题切分）") : question.source_context ? uiText("整卷参考解析（按题号查阅）") : (question.has_answer ? uiText("查看答案") : uiText("查看 Agent 解析")) }}</span><b>{{ answerOpen ? '↑' : '↓' }}</b>
            </button>
            <button type="button" class="fullscreen-trigger inline-fullscreen-trigger" :title="typeText('答案全屏', 'Answer full screen')" :aria-label="typeText('答案全屏', 'Answer full screen')" @click="openReader('answer')"><svg width="15" height="15" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M7 3H3v4m10-4h4v4M3 13v4h4m10-4v4h-4" /></svg></button>
            </div>
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
          <OriginalAnswer ref="originalAnswerReader" delegate-fullscreen @fullscreen="openReader('original')" :controls="readerControls" @action="readerAction" v-if="question.original_source?.has_answer" :key="question.original_source.uuid + question.uuid" :uuid="question.original_source.uuid" @opened="answerViewedThisRound = true" />
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
              <button type="button" :aria-pressed="usedHintThisRound" :class="{ active: usedHintThisRound }" @click="toggleUsedHint">{{ usedHintThisRound ? uiText("已使用提示") : uiText("未使用提示") }}</button>
              <span :class="{ compromised: usedHintThisRound || answerViewedThisRound }">{{ usedHintThisRound || answerViewedThisRound ? uiText("本轮不计为独立作答") : uiText("当前可计为独立作答") }}</span>
            </div>
            <button v-if="route.query.mode === 'method'" class="method-note-link" type="button" @click="noteOpen = true">{{ uiText("把调用的知识点和第一个关系式写入“题目笔记”") }}</button>
            <DiagnosisSelector compact :model-value="selectedErrors" :primary="primaryError" :options="errorOptions" @toggle="toggleError" />
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
              <div v-if="timerSyncStatus==='offline'||timerSyncStatus==='conflict'||timingRecoveryResult||pendingAttemptResult" class="timing-recovery" role="status">
                <button type="button" :disabled="saving||timerReconnecting" @click="reconnectQuestionTimer">{{ timerReconnecting?typeText('连接中…','Connecting…'):typeText('重新连接计时','Reconnect timer') }}</button>
                <button v-if="pendingAttemptResult" type="button" :disabled="saving" @click="record(pendingAttemptResult)">{{ typeText('重试上次作答','Retry previous submission') }}</button>
                <button v-if="timingRecoveryResult" type="button" :disabled="saving||timerReconnecting" @click="record(timingRecoveryResult,true)">{{ typeText('不记录本次用时，保存作答','Save answer without duration') }}</button>
                <small v-if="timingIssueReason">{{ typeText('计时状态','Timing status') }}: {{ timingIssueReason }}</small>
              </div>
              <small v-if="timerSyncStatus === 'offline' || timerSyncStatus === 'conflict'" class="note-draft-hint">{{ timerSyncStatus === 'conflict' ? typeText('计时同步冲突；本地进度已保留', 'Timing sync conflict; local progress retained') : typeText('离线计时已保存在本机', 'Offline timing saved on this device') }}</small><div class="question-timer" :class="{ active: !timingCountdown && !timingFinalized, saved: timingFinalized }"><span>{{ timingOmitted ? typeText("本次未记录用时","Duration omitted") : timingFinalized ? uiText("计时已保存") : timingCountdown ? uiText("计时准备") : uiText("本题用时") }}</span><strong>{{ timingOmitted ? '—' : timingFinalized || !timingCountdown ? formattedQuestionTime : `${timingCountdown} ${typeText('秒后开始', 'seconds until start')}` }}</strong></div>
              <NoteVisibility :note="note" :question-key="props.uuid">
              <p v-if="note && !noteOpen" class="note-preview" role="button" tabindex="0" @click="noteOpen = true" @keydown.enter="noteOpen = true">{{ note }}</p>
              <details class="note-field" :open="noteOpen" @toggle="toggleNote"><summary><span>{{ uiText("题目笔记 Note") }}</span><small>{{ noteSaveState === 'saving' ? uiText("保存中…") : noteSaveState === 'saved' ? uiText("已保存") : noteSaveState === 'error' ? uiText("保存失败") : noteSaveState === 'dirty' ? uiText("未保存") : note ? uiText("展开编辑") : uiText("添加笔记") }}</small></summary><textarea v-model="note" maxlength="20000" :placeholder="uiText('记录公式、错误原因、修正方法或下次检查点')" @input="cacheNoteDraft" /><span class="note-controls"><small class="note-draft-hint">{{ noteSaveState === 'saving' ? uiText("保存中…") : noteSaveState === 'saved' ? uiText("已保存到服务器") : noteSaveState === 'error' ? typeText('保存失败，请重试；离开页面前确认已保存。', 'Save failed. Retry and confirm it is saved before leaving this page.') : noteSaveState === 'dirty' ? uiText("未保存") : uiText("停止输入 5 秒后自动保存") }}</small><button type="button" class="save-note" :disabled="noteSaveState === 'saving'" @click="saveNote">{{ noteSaveState === 'saving' ? uiText("保存中…") : noteSaveState === 'error' ? uiText("重试保存") : uiText("保存笔记") }}</button></span></details>
              </NoteVisibility>
            </div>

          </div>
          <div class="answer-submit-bar answer-bar">
            <PracticeActionToolbar><template #primary><button class="correct primary-action" :class="{ selected: question.state === 'mastered' }" :disabled="saving" @click="record('correct')">{{ masteredAutoNext ? uiText("掌握并下一题") : uiText("标记已掌握") }}</button></template><template #secondary><button class="review" :class="{ selected: question.state === 'review' }" :disabled="saving" @click="record('review')">{{ uiText("待复习") }}{{ reviewAutoNext ? uiText("并下一题") : '' }}</button></template><template #more><details class="practice-more secondary-actions"><summary>{{ uiText("更多操作") }}</summary><div class="practice-more-menu"><button :disabled="saving || !question.can_undo" @click="undo">{{ uiText("撤销上次") }}</button><button class="destructive-action" :disabled="saving || question.state === 'unattempted'" @click="record('reset')">{{ uiText("重置本题状态") }}</button></div></details></template></PracticeActionToolbar>
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
            <header><strong>{{ uiText("翻题偏好") }}</strong><label>{{ uiText("前后翻题") }}<select v-model="nextMode"><option value="sequential">{{ uiText("顺序题") }}</option><option value="overdue">{{ uiText("红色到期复习题") }}</option><option value="review">{{ uiText("黄色近期复习题") }}</option><option value="unattempted">{{ uiText("未做题") }}</option></select></label></header>
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
.timing-recovery { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin: 4px 0 8px; font-size: 12px; }
.timing-recovery button, .source-current-question button, .source-tracking-toolbar button { min-height: 36px; padding: 8px; border: 0; border-radius: 6px; background: var(--surface-hover, var(--bg-sidebar)); color: var(--text-primary); font-size: 13px; cursor: pointer; }
.timing-recovery.in-reader { flex: none; margin: 0; padding: 8px max(12px, env(safe-area-inset-right)) 8px max(12px, env(safe-area-inset-left)); background: var(--bg-surface); border-bottom: 1px solid var(--border-subtle); }
.timing-recovery small { color: var(--text-secondary); overflow-wrap: anywhere; }
.source-current-question { display: grid; gap: 8px; margin-bottom: 12px; padding: 12px; border-bottom: 1px solid var(--border-subtle); background: var(--bg-surface); }
.source-current-question strong { font-size: 14px; }
.source-current-question small { font-size: 12px; color: var(--text-secondary); }
.source-tracking-toolbar { position: sticky; top: 8px; z-index: 8; display: flex; align-items: center; flex-wrap: wrap; gap: 8px; padding: 8px; background: var(--bg-surface); }
.source-tracking-toolbar strong { flex: 1 1 160px; font-size: 14px; color: var(--text-primary); }
.question-canvas.source-canvas { overflow: visible; }
.source-review-warning { padding: 12px; border-inline-start: 2px solid var(--warning); color: var(--warning); font-size: 14px; }
.answer-workflow { display: flex; flex-direction: column; min-width: 0; background: var(--bg-surface); }
.diagnosis-panel { display: grid; gap: 12px; margin: 0; padding: 12px; border: 0; border-bottom: 1px solid var(--border-subtle); background: transparent; }
.answer-workflow .answer-bar { border: 0; border-radius: 0; }
.answer-submit-bar { position: sticky; bottom: 0; z-index: 10; flex: none; padding: 8px 12px; background: var(--bg-surface); }
.answer-submit-bar :deep(.practice-action-toolbar) { margin-top: 0; }
.diagnosis-panel > header { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; }
.diagnosis-panel > header > div:first-child { display: grid; gap: 4px; }
.diagnosis-panel > header span { font-size: 16px; font-weight: 650; color: var(--text-primary); }
.diagnosis-status { color: var(--text-secondary); font-size: 12px; font-weight: 500; }
.diagnosis-status.draft, .diagnosis-status.saving { color: var(--warning); }
.diagnosis-status.saved { color: var(--success); }
.diagnosis-status.error { color: var(--danger); }
.diagnosis-actions { display: flex; align-items: center; gap: 4px; margin-left: auto; }
.diagnosis-actions button, .independence-flags button, .method-note-link { min-height: 36px; padding: 8px; border: 0; border-radius: 6px; color: var(--text-secondary); background: transparent; font-size: 13px; cursor: pointer; }
.diagnosis-actions button:hover, .independence-flags button:hover, .method-note-link:hover { background: var(--surface-hover, var(--bg-sidebar)); }
.diagnosis-body { display: grid; gap: 8px; min-width: 0; }
.independence-flags { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.independence-flags button.active { color: var(--text-primary); background: var(--surface-selected, var(--bg-surface-active)); }
.independence-flags span { font-size: 12px; color: var(--success); }
.independence-flags span.compromised { color: var(--warning); }
.primary-help { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin: 0; font-size: 13px; color: var(--text-secondary); }
.primary-help select, .diagnosis-advanced select, .page-turn-settings select { min-width: 0; max-width: 100%; min-height: 36px; padding: 4px 8px; border: 1px solid var(--border-default); border-radius: 6px; color: var(--text-primary); background: var(--bg-surface); font-size: 14px; }
.diagnosis-advanced { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
.diagnosis-advanced label { display: grid; gap: 8px; min-width: 0; font-size: 12px; color: var(--text-secondary); }
.diagnosis-advanced select { width: 100%; }
.diagnosis-body > footer { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px; padding-top: 8px; color: var(--text-secondary); border-top: 1px solid var(--border-subtle); font-size: 12px; }
.diagnosis-body > footer small { font-size: 12px; }
.attempt-history { display: grid; gap: 4px; padding-top: 8px; border-top: 1px solid var(--border-subtle); }
.attempt-history > button { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; min-height: 52px; padding: 8px; border: 0; border-radius: 6px; color: var(--text-primary); background: transparent; text-align: left; cursor: pointer; }
.attempt-history > button:hover { background: var(--surface-hover, var(--bg-sidebar)); }
.attempt-history > button span { display: grid; gap: 4px; }
.attempt-history > button span:last-child { text-align: right; }
.attempt-history p, .attempt-history small { margin: 4px 0; color: var(--text-secondary); font-size: 12px; }
.page-turn-settings { display: grid; gap: 8px; margin-top: 12px; padding: 12px 0; border-top: 1px solid var(--border-subtle); background: transparent; }
.page-turn-settings > header { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; }
.page-turn-settings > header strong { color: var(--text-primary); font-size: 14px; }
.page-turn-settings > header label { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; color: var(--text-secondary); font-size: 12px; }
.page-turn-settings select { max-width: 180px; }
.page-turn-settings-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 4px; }
.page-turn-settings-grid label { display: flex; align-items: center; gap: 8px; min-width: 0; min-height: 44px; padding: 8px; border-radius: 6px; color: var(--text-secondary); background: transparent; font-size: 13px; line-height: 1.4; cursor: pointer; }
.page-turn-settings-grid label:has(input:checked) { color: var(--text-primary); background: var(--surface-selected, var(--bg-surface-active)); }
.page-turn-settings-grid input { flex: none; width: 16px; height: 16px; margin: 0; accent-color: var(--accent); }
.page-turn-settings > small { color: var(--text-secondary); font-size: 12px; line-height: 1.4; }
.action-feedback { position: fixed; left: 50%; bottom: calc(env(safe-area-inset-bottom) + 16px); z-index: 80; max-width: calc(100vw - 24px); margin: 0; padding: 12px 16px; transform: translateX(-50%); border: 1px solid var(--border-subtle); border-radius: 8px; color: var(--text-primary); background: var(--surface-elevated, var(--bg-surface)); box-shadow: 0 4px 16px #0002; font-size: 14px; pointer-events: none; }
.asset-load-error { display: flex; align-items: center; justify-content: center; flex-wrap: wrap; gap: 12px; min-height: 110px; padding: 16px; border: 1px dashed var(--danger); border-radius: 6px; color: var(--danger); background: var(--bg-surface); }
.asset-load-error button { min-height: 44px; padding: 8px 12px; border: 0; border-radius: 6px; color: var(--text-primary); background: var(--surface-hover, var(--bg-sidebar)); cursor: pointer; }
.method-restart { display: grid; gap: 8px; padding: 12px; border-inline-start: 2px solid var(--warning); }
.method-restart label { display: grid; gap: 8px; color: var(--text-secondary); font-size: 13px; }
.method-restart input { min-width: 0; padding: 8px; color: var(--text-primary); background: var(--bg-surface); border: 1px solid var(--border-default); border-radius: 6px; }
.question-save-actions button { border: 0; color: var(--text-secondary); background: transparent; font-size: 13px; }
.question-save-actions button.active, .question-save-actions button + button.active { border: 0; color: var(--text-primary); background: var(--surface-selected, var(--bg-surface-active)); }
.question-save-actions button:hover:not(:disabled) { background: var(--surface-hover, var(--bg-sidebar)); }
.question-topbar button { border: 0; background: transparent; font-size: 13px; }
.question-topbar button:hover:not(:disabled) { background: var(--surface-hover, var(--bg-sidebar)); }
.note-field, .note-field textarea { font-size: 14px; }
.note-field summary { border: 0; background: transparent; }
.note-field summary small, .note-controls small { font-size: 12px; }
@media (pointer: coarse) { .diagnosis-actions button, .independence-flags button, .method-note-link, .primary-help select, .diagnosis-advanced select, .page-turn-settings select, .timing-recovery button, .save-note { min-height: 44px; } }
@media (max-width: 480px) { .diagnosis-advanced { grid-template-columns: 1fr; } .page-turn-settings-grid { grid-template-columns: 1fr; } }
@media (pointer: coarse) { .note-field textarea, .diagnosis-body select, .erratum-compose textarea, .erratum-compose select { font-size: 16px; } }
</style>
