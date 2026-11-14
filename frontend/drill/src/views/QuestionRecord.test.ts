// @vitest-environment jsdom
import { expect, it, vi } from 'vitest'
import source from './QuestionView.vue?raw'
import ts from 'typescript'
import { ApiError } from '../lib/api'
import { ForegroundTimer, type TimingReply } from '../../../shared/foregroundTimer'

// Exercise the production handler with controlled UI/timer dependencies, without
// mounting unrelated image, clipboard and router components.
const handler = source.slice(source.indexOf('async function record('), source.indexOf('\nfunction toggleError'))
const compiled = ts.transpileModule(handler, { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText
const ref = (value: unknown) => ({ value })
function setup() {
  const timer = { state: { pendingAttempt: undefined as Record<string,unknown>|undefined, submissionKey: null as string|null }, prepareSubmission:vi.fn().mockResolvedValue({status:'success',finalized:false}), rememberAttempt:vi.fn(), clearPreparedAttempt:vi.fn(), recordFailure:vi.fn(), archiveOmittedRound:vi.fn(), sync: vi.fn().mockResolvedValue(undefined), snapshot: vi.fn().mockReturnValue({timing_protocol:2,timing_key:'round-key',timing_owner:'owner',timing_sequence:2,timing_elapsed_ms:60000}), submissionKey: vi.fn().mockReturnValue('stable-key'), finish: vi.fn(), resumeAfterFailure: vi.fn() }
  const scope = {
    writeLocal:vi.fn(),cacheNoteDraft:vi.fn(),
    ApiError,timingRecoveryResult:ref(null),timerFailureMessage:()=> 'Timing not connected; answer not submitted',
    saving: ref(false), question: ref({ uuid: 'q', state_version: 7 }), props: { uuid: 'q' },
    studyTimerMode: ref('off'), studyTimerGuard: ref(null),
    diagnosisSaveTimer: 0, diagnosisSaveSequence: 0, operationSequence: 0,
    practiceTimer: timer, note: ref('note'), masteredAutoNext: ref(false), reviewAutoNext: ref(false),
    previewNavigation: ref({}), previewContext: ref(null), isPreviewEntry: ref(false), previewNavigationError: ref(''), previewNavigationTask: Promise.resolve(),
    pageTurnCopyMode: ref('off'), pendingSubmissionKey: ref(null), recordedQuestionSeconds: () => 60,
    usedHintThisRound: ref(false), answerViewedThisRound: ref(false), knowledgeLevel: ref(null), methodLevel: ref(null), executionLevel: ref(null),
    selectedErrors: ref([]), primaryError: ref(null), post: vi.fn().mockResolvedValue({ note_conflict: false }),
    discardNoteDraft: vi.fn(), applyState: vi.fn(), notifyPracticeTrendChanged: vi.fn(),
    editingAttemptId: ref(null), diagnosisSaveState: ref('idle'), actionFeedbackTimer: 0, actionFeedback: ref(''), noteSaveState: ref('idle'),
    timingOmitted:ref(false),timingFinalized: ref(false), questionTimerInterval: 0, error: ref(''), typeText: (_zh: string, en: string) => en,
  }
  const record = new Function('scope', `with (scope) { ${compiled}; return record }`)(scope) as (result: string,omit?:boolean) => Promise<void>
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
    effectiveNextMode: ref('review'), topNextTarget: ref('next-q'), nextQuestionTarget: vi.fn().mockReturnValue('next-q'),
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

it('does not post an Attempt after a true ownership conflict and preserves drafts and submission identity', async()=>{
  const {scope,timer,record}=setup()
  timer.prepareSubmission.mockResolvedValue({status:'conflict',issue:{reason:'owner_mismatch',can_reclaim:false}})
  scope.pendingSubmissionKey.value='existing-submission-key'
  await record('correct')
  expect(scope.post).not.toHaveBeenCalled();expect(timer.snapshot).not.toHaveBeenCalled()
  expect(scope.pendingSubmissionKey.value).toBe('existing-submission-key')
  expect(scope.note.value).toBe('note');expect(scope.discardNoteDraft).not.toHaveBeenCalled()
  expect(scope.timingRecoveryResult.value).toBe('correct')
  expect(scope.error.value).toContain('not submitted')
})
it('only omits duration after explicit choice and keeps normal diagnosis and submission data',async()=>{
  const {scope,timer,record}=setup()
  await record('review',true)
  expect(timer.prepareSubmission).not.toHaveBeenCalled()
  const body=scope.post.mock.calls[0]![1]
  expect(body).toMatchObject({timing_protocol:2,timing_omit:true,timing_key:'round-key',result:'review',note:'note',submission_key:'stable-key'})
  expect(body).not.toHaveProperty('time_spent_seconds')
  expect(timer.archiveOmittedRound).toHaveBeenCalledOnce()
})
it('retries the exact prepared request after an unknown network outcome without blocking on finalized timing',async()=>{
  const {scope,timer,record}=setup()
  const body={result:'correct',note:'note',timing_protocol:2,timing_key:'old-round',timing_owner:'old-document',timing_sequence:9,timing_elapsed_ms:60000,submission_key:'pending-key',knowledge_level:null,method_level:null,execution_level:null,used_hint:false,viewed_answer:false,error_codes:[],primary_error:null}
  timer.state.pendingAttempt=body
  timer.prepareSubmission.mockResolvedValue({status:'conflict',issue:{reason:'timing_finalized',can_reclaim:false}})
  await record('correct')
  expect(timer.prepareSubmission).not.toHaveBeenCalled();expect(timer.snapshot).not.toHaveBeenCalled()
  expect(scope.post).toHaveBeenCalledWith('/api/drill/questions/q/attempts/',body)
  expect(timer.finish).toHaveBeenCalledOnce()
})
it('blocks a different answer while the prior outcome is unconfirmed',async()=>{
  const {scope,timer,record}=setup()
  timer.state.pendingAttempt={result:'review',submission_key:'old-key',note:'note'}
  await record('correct')
  expect(scope.post).not.toHaveBeenCalled()
  expect(scope.error.value).toContain('Retry the previous submission first')
  expect(timer.clearPreparedAttempt).not.toHaveBeenCalled()
})
it('retains later Note and diagnosis edits when the old prepared submission is acknowledged',async()=>{
  const {scope,timer,record}=setup()
  timer.state.pendingAttempt={result:'review',submission_key:'old-key',note:'old note',knowledge_level:1,method_level:null,execution_level:null,used_hint:false,viewed_answer:false,error_codes:[],primary_error:null}
  scope.note.value='new unsaved note';scope.knowledgeLevel.value=2
  scope.applyState.mockImplementation(()=>{scope.note.value='old note'})
  await record('review')
  expect(scope.note.value).toBe('new unsaved note')
  expect(scope.cacheNoteDraft).toHaveBeenCalled()
  expect(scope.discardNoteDraft).not.toHaveBeenCalled()
  expect(scope.writeLocal).toHaveBeenCalledWith(expect.any(String),expect.objectContaining({pending_edits:true,knowledge:2}))
  expect(scope.error.value).toContain('Later note or diagnosis edits are retained as drafts')
})

it('deduplicates after a real timer finalizes, the response is lost, and the page is restored',async()=>{
  localStorage.clear()
  let finalized=false,created=0
  const replies=new Map<string,unknown>()
  const timingApi=async<T>(_url:string,options?:RequestInit)=>{
    const input=JSON.parse(String(options?.body))
    return {protocol:2,timing_key:input.timing_key,owner:input.owner,elapsed_ms:input.elapsed_ms,countdown_ms:input.countdown_ms,sequence:input.sequence,finalized,local_base_valid:true} as TimingReply as T
  }
  const {scope,record}=setup()
  const actual=new ForegroundTimer('retry-test-user','drill','q',timingApi)
  await actual.activate()
  Object.assign(scope,{practiceTimer:actual})
  scope.post.mockImplementation(async(_url,body)=>{
    const key=body.submission_key as string
    if(replies.has(key))return replies.get(key)
    created+=1;finalized=true
    replies.set(key,{note:'note',note_conflict:false,attempt_count:1,state:'mastered'})
    throw new Error('Response lost after commit')
  })
  await record('correct')
  const submission=actual.state.submissionKey
  expect(actual.state.pendingAttempt?.submission_key).toBe(submission)
  await actual.activate()
  expect(actual.state.finalized).toBe(true)
  const restored=new ForegroundTimer('retry-test-user','drill','q',timingApi)
  expect(restored.state.submissionKey).toBe(submission)
  Object.assign(scope,{practiceTimer:restored})
  await record('correct')
  expect(scope.post).toHaveBeenCalledTimes(2)
  expect(created).toBe(1)
  expect(restored.state.pendingAttempt).toBeUndefined()
  expect(restored.state.submissionKey).toBeNull()
})

it('saves the answer before awaiting a slow preview-navigation read',async()=>{
 const {scope,timer,record}=setup()
 let complete!:()=>void
 const navigation=new Promise<void>(resolve=>{complete=resolve})
 scope.masteredAutoNext.value=true
 const goToNext=vi.fn().mockResolvedValue(undefined)
 Object.assign(scope,{previewContext:ref({source:'attempts'}),isPreviewEntry:ref(true),previewNavigationTask:navigation,topNextTarget:ref('next-q'),effectiveNextMode:ref('sequential'),goToNext})
 const pending=record('correct')
 await vi.waitFor(()=>expect(scope.post).toHaveBeenCalledOnce())
 expect(timer.finish).toHaveBeenCalledOnce()
 expect(goToNext).not.toHaveBeenCalled()
 complete();await pending
 expect(goToNext).toHaveBeenCalledWith('sequential',false)
})

it('cancels a timer reminder before preparing or saving an attempt',async()=>{
 const {scope,timer,record}=setup();scope.studyTimerMode.value='remind'
 scope.studyTimerGuard.value={ensure:vi.fn().mockResolvedValue(false)}
 await record('correct')
 expect(scope.post).not.toHaveBeenCalled();expect(timer.prepareSubmission).not.toHaveBeenCalled();expect(scope.saving.value).toBe(false)
})
it('saves a review after the timer guard allows it',async()=>{
 const {scope,timer,record}=setup();scope.studyTimerMode.value='remind'
 const ensure=vi.fn().mockResolvedValue(true);scope.studyTimerGuard.value={ensure}
 await record('review')
 expect(ensure).toHaveBeenCalledOnce();expect(timer.prepareSubmission).toHaveBeenCalledOnce();expect(scope.post).toHaveBeenCalledOnce()
})
