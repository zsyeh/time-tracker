// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import DiagnosticDashboardView from './DiagnosticDashboardView.vue'
import { api } from '../lib/api'

const chartMocks = vi.hoisted(() => ({ setOption: vi.fn(), resize: vi.fn(), dispose: vi.fn(), init: vi.fn() }))
vi.mock('echarts/core', () => ({ use: vi.fn(), init: chartMocks.init }))
vi.mock('echarts/charts', () => ({ BarChart: {}, LineChart: {} }))
vi.mock('echarts/components', () => ({ GridComponent: {}, LegendComponent: {}, TooltipComponent: {} }))
vi.mock('echarts/renderers', () => ({ CanvasRenderer: {} }))
vi.mock('../lib/api', () => ({ api: vi.fn() }))

let app: App | undefined
let host: HTMLDivElement
const observed: Element[] = []
let observer: { observe: (element: Element) => void; disconnect: ReturnType<typeof vi.fn> } | undefined
const payload = {
  workspace: 'drill', range: { start: '2026-11-05', end: '2026-11-11' },
  today: { new_questions: 1, review_questions: 1, completed_questions: 2, submissions: 2, first_sample: 1, first_independent_correct: 1 },
  period_activity: { daily_unique_questions: 4, submissions: 5, unique_questions: 3, diagnosed_attempts: 2, legacy_unknown_attempts: 0 },
  activity: [{ date: '2026-11-11', daily_unique_questions: 2, submissions: 3, new_questions: 1, review_questions: 1, diagnosed_questions: 1, legacy_unknown_questions: 0 }],
  metrics: {
    first_independent_accuracy: { value: 100, numerator: 1, sample: 1 }, second_independent_accuracy: { value: null, numerator: 0, sample: 0 },
    pending_redo_count: 0, error_recurrence_rate: { value: null, numerator: 0, sample: 0 }, method_start_failure_rate: { value: 0, numerator: 0, sample: 1 },
  },
  error_distribution: [], due_count: 0,
  trend: [{ date: '2026-11-11', first_sample: 1, first_independent_correct: 1, second_sample: 0, second_independent_correct: 0 }],
  courses: [], repeated_topics: [], topic_trends: [], notice: '',
}

beforeEach(() => {
  vi.clearAllMocks(); observed.length = 0
  chartMocks.init.mockReturnValue(chartMocks)
  vi.stubGlobal('ResizeObserver', class {
    disconnect = vi.fn()
    constructor(callback: ResizeObserverCallback) { observer = this; void callback }
    observe(element: Element) { observed.push(element) }
  })
  vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => window.setTimeout(() => callback(0), 0))
  vi.stubGlobal('cancelAnimationFrame', (id: number) => window.clearTimeout(id))
})
afterEach(() => { app?.unmount(); app = undefined; host?.remove(); vi.restoreAllMocks(); vi.unstubAllGlobals() })
async function flush() { await Promise.resolve(); await nextTick(); await new Promise(resolve => setTimeout(resolve, 5)); await nextTick() }

it('observes charts after async data creates them and resizes on orientation and viewport changes', async () => {
  let resolve!: (value: typeof payload) => void
  vi.mocked(api).mockImplementationOnce(() => new Promise(finish => { resolve = finish }))
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/diagnostics', component: DiagnosticDashboardView }] })
  await router.push('/diagnostics'); await router.isReady()
  host = document.createElement('div'); document.body.append(host)
  app = createApp({ template: '<router-view />' }); app.use(router); app.mount(host)
  await flush()
  expect(observed).toHaveLength(0)
  resolve(payload); await flush()
  expect(observed).toContain(host.querySelector('.activity-chart'))
  expect(observed).toContain(host.querySelector('.ability-chart'))
  const before = chartMocks.resize.mock.calls.length
  window.dispatchEvent(new Event('orientationchange')); await flush()
  expect(chartMocks.resize.mock.calls.length).toBeGreaterThan(before)
  app.unmount(); app = undefined
  expect(observer?.disconnect).toHaveBeenCalledOnce()
})
