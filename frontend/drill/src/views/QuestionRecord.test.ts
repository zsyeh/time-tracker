// @vitest-environment jsdom
import { expect, it, vi } from 'vitest'
import source from './QuestionView.vue?raw'
import ts from 'typescript'

// Exercise the production handler with controlled UI/timer dependencies, without
// mounting unrelated image, clipboard and router components.
const handler = source.slice(source.indexOf('async function record('), source.indexOf('\nfunction toggleError'))
const compiled = ts.transpileModule(handler, { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText
const ref = (value: unknown) => ({ value })
function setup() {
  const timer = { sync: vi.fn().mockResolvedValue(undefined), snapshot: vi.fn().mockReturnValue({}), submissionKey: vi.fn().mockReturnValue('stable-key'), finish: vi.fn(), resumeAfterFailure: vi.fn() }
  const scope = {
    saving: ref(false), question: ref({ uuid: 'q', state_version: 7 }), props: { uuid: 'q' },
    diagnosisSaveTimer: 0, diagnosisSaveSequence: 0, operationSequence: 0,
    practiceTimer: timer, note: ref('note'), masteredAutoNext: ref(false), reviewAutoNext: ref(false),
    pageTurnCopyMode: ref('off'), pendingSubmissionKey: ref(null), recordedQuestionSeconds: () => 60,
    usedHintThisRound: ref(false), answerViewedThisRound: ref(false), knowledgeLevel: ref(null), methodLevel: ref(null), executionLevel: ref(null),
    selectedErrors: ref([]), primaryError: ref(null), post: vi.fn().mockResolvedValue({ note_conflict: false }),
    discardNoteDraft: vi.fn(), applyState: vi.fn(), notifyPracticeTrendChanged: vi.fn(),
    editingAttemptId: ref(null), diagnosisSaveState: ref('idle'), actionFeedbackTimer: 0, actionFeedback: ref(''), noteSaveState: ref('idle'),
    timingFinalized: ref(false), questionTimerInterval: 0, error: ref(''), typeText: (_zh: string, en: string) => en,
  }
  const record = new Function('scope', `with (scope) { ${compiled}; return record }`)(scope) as (result: string) => Promise<void>
  return { scope, timer, record }
}
it('does not report an acknowledged attempt as failed when statistics refresh fails', async () => {
  const { scope, timer, record } = setup()
  scope.notifyPracticeTrendChanged.mockImplementation(() => { throw new Error('channel unavailable') })
  await record('correct')
  expect(scope.post).toHaveBeenCalledTimes(1)
  expect(scope.question.value).toBeTruthy()
  expect(scope.timingFinalized.value).toBe(true)
  expect(scope.pendingSubmissionKey.value).toBeNull()
  expect(timer.resumeAfterFailure).not.toHaveBeenCalled()
  expect(scope.error.value).toBe('')
})
it('retains saved status and stops timing if a subsequent UI operation fails', async () => {
  const { scope, timer, record } = setup()
  scope.applyState.mockImplementation(() => { throw new Error('UI unavailable') })
  await record('review')
  expect(timer.finish).toHaveBeenCalledOnce()
  expect(timer.resumeAfterFailure).not.toHaveBeenCalled()
  expect(scope.pendingSubmissionKey.value).toBeNull()
  expect(scope.error.value).toContain('Answer saved; follow-up action failed')
})
it('retains the same submission key after a network failure and blocks a simultaneous click', async () => {
  const { scope, timer, record } = setup()
  let reject!: (reason: Error) => void
  scope.post.mockImplementationOnce(() => new Promise((_resolve, fail) => { reject = fail }))
  const pending = record('correct')
  await Promise.resolve(); await Promise.resolve()
  await record('correct')
  expect(scope.post).toHaveBeenCalledTimes(1)
  reject(new Error('network unavailable')); await pending
  expect(scope.pendingSubmissionKey.value).toBe('stable-key')
  expect(timer.resumeAfterFailure).toHaveBeenCalledOnce()
  await record('correct')
  expect(scope.post.mock.calls[1]![1].submission_key).toBe('stable-key')
})
it('keeps the attempt saved when the next-question operation rejects', async () => {
  const { scope, timer, record } = setup()
  scope.masteredAutoNext.value = true
  Object.assign(scope, {
    nextMode: ref('review'), nextQuestionTarget: vi.fn().mockReturnValue('next-q'),
    goToNext: vi.fn().mockRejectedValue(new Error('navigation unavailable')),
  })
  await record('correct')
  expect(scope.post).toHaveBeenCalledOnce()
  expect(scope.pendingSubmissionKey.value).toBeNull()
  expect(scope.timingFinalized.value).toBe(true)
  expect(timer.finish).toHaveBeenCalledOnce()
  expect(timer.resumeAfterFailure).not.toHaveBeenCalled()
  expect(scope.error.value).toContain('Answer saved; follow-up action failed: navigation unavailable')
})

it('applies authoritative UI state even if cache invalidation unexpectedly throws', () => {
  const fn = source.slice(source.indexOf('function applyState('), source.indexOf('\nasync function record('))
  const code = ts.transpileModule(fn, { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText
  const scope = { props: { uuid: 'q' }, question: ref({ uuid: 'q', state: 'unattempted' }), note: ref('draft'), patchQuestionState: vi.fn(() => { throw new Error('cache unavailable') }) }
  const apply = new Function('scope', `with (scope) { ${code}; return applyState }`)(scope)
  expect(() => apply({ state: 'review', note: 'server note', attempt_count: 2 })).not.toThrow()
  expect(scope.question.value).toMatchObject({ state: 'review', note: 'server note', attempt_count: 2 })
  expect(scope.note.value).toBe('server note')
  apply({ state: 'mastered', note: 'other question' }, 'different-uuid')
  expect(scope.question.value).toMatchObject({ state: 'review', note: 'server note' })
})
