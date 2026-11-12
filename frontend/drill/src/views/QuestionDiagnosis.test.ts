// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import ts from 'typescript'
import source from './QuestionView.vue?raw'

const ref = <T>(value: T) => ({ value })
const extract = (start: string, end: string, name: string, scope: object) => {
  const code = source.slice(source.indexOf(start), source.indexOf(end, source.indexOf(start)))
  return new Function('scope', `with(scope) { ${ts.transpileModule(code, { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText}; return ${name} }`)(scope)
}
afterEach(() => vi.useRealTimers())
function setup() {
  const scope = {
    selectedErrors: ref<string[]>([]), primaryError: ref<string | null>(null),
    knowledgeLevel: ref<string | null>('K1'), methodLevel: ref<string | null>('M0'), executionLevel: ref<string | null>('E1'),
    usedHintThisRound: ref(true), answerViewedThisRound: ref(false), diagnosisHydrating: false,
    diagnosisSaveTimer: 0, diagnosisSaveSequence: 0, editingAttemptId: ref<number | null>(null),
    props: { uuid: 'q1' }, diagnosisSaveState: ref('idle'), attemptHistory: ref([{ id: 1 }, { id: 2 }]),
    question: ref<{ latest_diagnosis: { id: number } }>({ latest_diagnosis: { id: 1 } }), error: ref(''),
    api: vi.fn().mockResolvedValue({ id: 1, primary_error: 'B2' }),
  }
  const toggle = extract('function toggleError(', '\nfunction diagnosisPayload(', 'toggleError', scope)
  const changed = extract('function diagnosisPayload(', '\nwatch([\n  selectedErrors', 'diagnosisChanged', scope)
  return { scope, toggle, changed }
}
it('preserves insertion order, automatic first primary and a manually chosen primary', () => {
  const { scope, toggle } = setup()
  toggle('B2'); toggle('A'); toggle('C1')
  expect(scope.selectedErrors.value).toEqual(['B2', 'A', 'C1'])
  expect(scope.primaryError.value).toBe('B2')
  scope.primaryError.value = 'C1'
  toggle('A'); expect(scope.primaryError.value).toBe('C1')
  toggle('C1'); expect(scope.primaryError.value).toBe('B2')
  toggle('B2'); expect(scope.primaryError.value).toBeNull()
})
it('keeps current-round diagnosis as a draft and saves a historical Attempt after exactly 550ms', async () => {
  vi.useFakeTimers()
  const { scope, toggle, changed } = setup()
  toggle('B2'); changed()
  await vi.advanceTimersByTimeAsync(1000)
  expect(scope.diagnosisSaveState.value).toBe('draft'); expect(scope.api).not.toHaveBeenCalled()
  scope.editingAttemptId.value = 1; changed()
  await vi.advanceTimersByTimeAsync(549); expect(scope.api).not.toHaveBeenCalled()
  await vi.advanceTimersByTimeAsync(1)
  expect(scope.api).toHaveBeenCalledWith('/api/drill/attempts/1/diagnosis/', {
    method: 'PATCH', body: JSON.stringify({ error_codes: ['B2'], primary_error: 'B2', knowledge_level: 'K1', method_level: 'M0', execution_level: 'E1', used_hint: true, viewed_answer: false, is_independent: false }),
  })
  expect(scope.attemptHistory.value).toEqual([{ id: 1, primary_error: 'B2' }, { id: 2 }])
  expect(scope.diagnosisSaveState.value).toBe('saved')
})
it('debounces historical edits and ignores a response for a question that has already changed', async () => {
  vi.useFakeTimers()
  const { scope, toggle, changed } = setup()
  let resolve!: (value: object) => void
  scope.api.mockImplementation(() => new Promise(done => { resolve = done }))
  scope.editingAttemptId.value = 1
  toggle('A'); changed(); await vi.advanceTimersByTimeAsync(500)
  toggle('B2'); changed(); await vi.advanceTimersByTimeAsync(500)
  expect(scope.api).not.toHaveBeenCalled()
  await vi.advanceTimersByTimeAsync(50); expect(scope.api).toHaveBeenCalledOnce()
  scope.props.uuid = 'q2'; resolve({ id: 1, primary_error: 'A' }); await Promise.resolve(); await Promise.resolve()
  expect(scope.attemptHistory.value).toEqual([{ id: 1 }, { id: 2 }])
})
it('preserves search filters and index generation through consecutive question navigation', () => {
  const query = { q: 'Fourier', state: 'mastered', status: 'review', favorite: '1', review_later: '1', sort: 'relevance', search_version: '2', index_version: '1:alias:gen', document: 'book1', unexpected: 'ignore' }
  const navigation = extract('function navigationQuery()', '\nfunction navigationQueryString()', 'navigationQuery', { previewContext: ref(null), router: { currentRoute: ref({ query }) } })
  const { unexpected: _ignored, ...expected } = query
  expect(navigation()).toEqual(expected)
})

it('returns to the original Practice page without sending page as question navigation order', () => {
  const push = vi.fn()
  const navigationQuery = () => ({ q: 'Fourier', practice_page: '3', sort: 'relevance', index_version: 'g1' })
  const back = extract('function backToEntryPoint()', '\nconst question =', 'backToEntryPoint', { previewContext: ref(null), route: { query: {} }, router: { push }, navigationQuery })
  back()
  expect(push).toHaveBeenCalledWith({ path: '/practice', query: { q: 'Fourier', page: '3', sort: 'relevance', index_version: 'g1' } })
})
