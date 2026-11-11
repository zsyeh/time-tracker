// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import HeatmapView from './HeatmapView.vue'
import { api } from '../lib/api'

vi.mock('../lib/api', () => ({ api: vi.fn() }))
vi.mock('../lib/workspace', () => ({ cachedHeatmap: vi.fn(() => null), storeHeatmap: vi.fn() }))
vi.mock('../components/LearningSharePanel.vue', () => ({ default: { template: '<div />' } }))

const question = {
  uuid: 'q-1', order: 1, label: 'Question 1', topic: 'Topic', year: 2024,
  variant: '', attempt_count: 1, latest_result: null, review_overdue: false,
  state: 'review', source_indexed: true, type_group: 'small',
}
const payload = {
  question_count: 1, topic_count: 0,
  statistics: { attempted_question_count: 1, mastered_question_count: 0, review_question_count: 1 },
  groups: [{ document_id: 7, document: 'Book A', questions: [question], topics: [],
    statistics: { attempted_question_count: 1, mastered_question_count: 0, review_question_count: 1, coverage_percent: 100 } }],
}

let app: App | undefined
let host: HTMLDivElement
beforeEach(() => {
  vi.clearAllMocks()
  sessionStorage.clear()
  host = document.createElement('div')
  document.body.append(host)
  vi.mocked(api).mockResolvedValue(payload)
  vi.stubGlobal('scrollTo', vi.fn())
  HTMLElement.prototype.scrollIntoView = vi.fn()
})
afterEach(() => { app?.unmount(); app = undefined; host.remove(); vi.unstubAllGlobals() })

it('keeps the core heatmap selection and scroll position after opening a question', async () => {
  const router = createRouter({ history: createMemoryHistory(), routes: [
    { path: '/core-heatmap', component: HeatmapView },
    { path: '/practice/:uuid', component: { template: '<div />' } },
  ] })
  await router.push('/core-heatmap?scope=past_exam&course=math&material=ready&question=q-1')
  await router.isReady()
  app = createApp(HeatmapView, { selectedOnly: true, coreOnly: true })
  app.use(router).mount(host)
  await nextTick(); await nextTick(); await nextTick()
  Object.defineProperty(window, 'scrollY', { configurable: true, value: 360 })
  host.querySelector<HTMLButtonElement>('[data-question-uuid="q-1"]')!.click()
  await nextTick(); await new Promise(resolve => setTimeout(resolve, 0))
  const saved = JSON.parse(sessionStorage.getItem('drill.heatmap.return.v2.core') || '{}')
  expect(saved).toMatchObject({ scope: 'past_exam', course: 'math', material: 'ready', questionUuid: 'q-1', scrollY: 360 })
  expect(router.currentRoute.value.path).toBe('/practice/q-1')
  app.unmount(); app = undefined
  await router.push('/core-heatmap?scope=past_exam&course=math&material=ready&question=q-1')
  app = createApp(HeatmapView, { selectedOnly: true, coreOnly: true })
  app.use(router).mount(host)
  await nextTick(); await nextTick(); await nextTick()
  await vi.waitFor(() => expect(window.scrollTo).toHaveBeenCalledWith({ top: 360, behavior: 'auto' }))
  expect(host.querySelector('[data-question-uuid="q-1"]')?.classList.contains('selected')).toBe(true)
})

it('dims other states without changing the matrix and locates the next unattempted question', async () => {
  vi.mocked(api).mockResolvedValue({ ...payload, question_count: 4, groups: [{ ...payload.groups[0], questions: [
    question,
    { ...question, uuid: 'q-2', order: 2, label: 'Question 2', state: 'unattempted', attempt_count: 0, source_indexed: false },
    { ...question, uuid: 'q-3', order: 3, label: 'Question 3', state: 'mastered', source_indexed: false },
    { ...question, uuid: 'q-4', order: 4, label: 'Question 4', state: 'unattempted', attempt_count: 0, source_indexed: false },
  ] }] })
  const router = createRouter({ history: createMemoryHistory(), routes: [
    { path: '/selected-heatmap', component: HeatmapView },
    { path: '/practice/:uuid', component: { template: '<div />' } },
  ] })
  await router.push('/selected-heatmap?scope=past_exam&type_group=small')
  await router.isReady()
  app = createApp(HeatmapView, { selectedOnly: true })
  app.use(router).mount(host)
  await new Promise(resolve => setTimeout(resolve, 0))
  const cells = () => [...host.querySelectorAll<HTMLElement>('[data-question-uuid]')]
  expect(cells()).toHaveLength(4)
  host.querySelector<HTMLButtonElement>('.heatmap-state-filters button:nth-child(2)')!.click()
  await nextTick()
  expect(cells()).toHaveLength(4)
  expect(cells().map(cell => cell.classList.contains('dimmed'))).toEqual([true, false, true, false])
  host.querySelector<HTMLButtonElement>('.heatmap-next')!.click()
  await nextTick()
  expect(host.querySelector('[data-question-uuid="q-2"]')?.classList.contains('selected')).toBe(true)
  expect(HTMLElement.prototype.scrollIntoView).toHaveBeenCalled()
  expect(host.querySelector('[role="status"]')?.textContent).toContain('Next unattempted')
  host.querySelector<HTMLButtonElement>('.heatmap-next')!.click()
  await nextTick()
  expect(host.querySelector('[data-question-uuid="q-4"]')?.classList.contains('selected')).toBe(true)
})

it('restores a returned selection only after an uncached heatmap finishes rendering', async () => {
  let resolvePayload!: (value: typeof payload) => void
  vi.mocked(api).mockReturnValue(new Promise(resolve => { resolvePayload = resolve }) as ReturnType<typeof api>)
  sessionStorage.setItem('drill.heatmap.return.v2.core', JSON.stringify({
    scope: 'all', typeGroup: '', course: '', material: 'ready', quickState: 'review', questionUuid: 'q-1', scrollY: 280,
  }))
  const router = createRouter({ history: createMemoryHistory(), routes: [
    { path: '/core-heatmap', component: HeatmapView },
  ] })
  await router.push('/core-heatmap?question=q-1')
  await router.isReady()
  app = createApp(HeatmapView, { selectedOnly: true, coreOnly: true })
  app.use(router).mount(host)
  await nextTick()
  expect(host.querySelector('[data-question-uuid="q-1"]')).toBeNull()
  expect(window.scrollTo).not.toHaveBeenCalled()
  resolvePayload(payload)
  await vi.waitFor(() => expect(window.scrollTo).toHaveBeenCalledWith({ top: 280, behavior: 'auto' }))
  expect(host.querySelector('[data-question-uuid="q-1"]')?.classList.contains('selected')).toBe(true)
  expect(host.querySelector('.heatmap-state-filters button:nth-child(3)')?.getAttribute('aria-pressed')).toBe('true')
})
