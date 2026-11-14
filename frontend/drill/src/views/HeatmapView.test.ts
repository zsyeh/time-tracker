// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import HeatmapView from './HeatmapView.vue'
import { accountPreferences } from '../../../shared/preferences/store'
import { preferenceDefaults } from '../../../shared/preferences/schema'
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
afterEach(() => { app?.unmount(); accountPreferences.reset(true); accountPreferences.dispose(); app = undefined; host.remove(); vi.unstubAllGlobals() })

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

it('retains the original browsing position after consecutive questions while selecting the current question', async () => {
  vi.mocked(api).mockResolvedValue({ ...payload, groups: [{ ...payload.groups[0], questions: [question, { ...question, uuid: 'q-2', order: 2 }] }] })
  sessionStorage.setItem('drill.heatmap.return.v2.selected', JSON.stringify({ scope: 'all', typeGroup: '', course: '', material: 'ready', quickState: 'review', questionUuid: 'q-1', scrollY: 420 }))
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/selected-heatmap', component: HeatmapView }] })
  await router.push('/selected-heatmap?question=q-2')
  app = createApp(HeatmapView, { selectedOnly: true }); app.use(router).mount(host)
  await vi.waitFor(() => expect(window.scrollTo).toHaveBeenCalledWith({ top: 420, behavior: 'auto' }))
  expect(host.querySelector('[data-question-uuid="q-2"]')?.getAttribute('aria-pressed')).toBe('true')
  expect(host.querySelector('.heatmap-state-filters button:nth-child(3)')?.getAttribute('aria-pressed')).toBe('true')
})

it('does not override a user scroll when an uncached return finishes late', async () => {
  let resolve!: (value: typeof payload) => void
  vi.mocked(api).mockReturnValue(new Promise(done => { resolve = done }) as ReturnType<typeof api>)
  sessionStorage.setItem('drill.heatmap.return.v2.selected', JSON.stringify({ scope: 'all', typeGroup: '', course: '', material: 'ready', questionUuid: 'q-1', scrollY: 420 }))
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/selected-heatmap', component: HeatmapView }] })
  await router.push('/selected-heatmap?question=q-1')
  app = createApp(HeatmapView, { selectedOnly: true }); app.use(router).mount(host)
  window.dispatchEvent(new Event('wheel'))
  resolve(payload)
  await new Promise(done => setTimeout(done, 70))
  expect(window.scrollTo).not.toHaveBeenCalled()
  expect(HTMLElement.prototype.scrollIntoView).not.toHaveBeenCalled()
  expect(host.querySelector('[data-question-uuid="q-1"]')?.getAttribute('aria-pressed')).toBe('true')
})

it('aborts an old scope request and ignores its late error after a new scope has loaded', async () => {
  let reject!: (reason: Error) => void
  vi.mocked(api).mockReturnValueOnce(new Promise((_done, fail) => { reject = fail }) as ReturnType<typeof api>).mockResolvedValue(payload)
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/selected-heatmap', component: HeatmapView }] })
  await router.push('/selected-heatmap')
  app = createApp(HeatmapView, { selectedOnly: true }); app.use(router).mount(host)
  host.querySelector<HTMLButtonElement>('.heat-scope button:nth-child(2)')!.click()
  await nextTick(); await nextTick()
  expect((vi.mocked(api).mock.calls[0]![1]?.signal as AbortSignal).aborted).toBe(true)
  reject(new Error('stale network error'))
  await vi.waitFor(() => expect(host.querySelectorAll('[data-question-uuid]')).toHaveLength(1))
  expect(host.textContent).not.toContain('stale network error')
  await vi.waitFor(() => expect(router.currentRoute.value.query.scope).toBe('past_exam'))
})

it('does not consume another account return state for the same question', async () => {
  sessionStorage.setItem('drill.heatmap.return.v2.selected', JSON.stringify({ userId: 'different-account', workspace: 'drill', scope: 'all', typeGroup: '', course: '', material: 'ready', quickState: 'review', questionUuid: 'q-1', scrollY: 999 }))
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/selected-heatmap', component: HeatmapView }] })
  await router.push('/selected-heatmap?question=q-1')
  app = createApp(HeatmapView, { selectedOnly: true }); app.use(router).mount(host)
  await vi.waitFor(() => expect(HTMLElement.prototype.scrollIntoView).toHaveBeenCalled())
  expect(window.scrollTo).not.toHaveBeenCalled()
  expect(host.querySelector('.heatmap-state-filters button:first-child')?.getAttribute('aria-pressed')).toBe('true')
})

it('restores a warm cached return before a slow refresh completes', async () => {
  const { cachedHeatmap } = await import('../lib/workspace')
  vi.mocked(cachedHeatmap).mockReturnValueOnce(payload)
  vi.mocked(api).mockReturnValue(new Promise(() => {}) as ReturnType<typeof api>)
  sessionStorage.setItem('drill.heatmap.return.v2.selected', JSON.stringify({
    scope: 'all', typeGroup: '', course: '', material: 'ready', questionUuid: 'q-1', scrollY: 320,
  }))
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/selected-heatmap', component: HeatmapView }] })
  await router.push('/selected-heatmap?question=q-1')
  app = createApp(HeatmapView, { selectedOnly: true }); app.use(router).mount(host)
  await vi.waitFor(() => expect(window.scrollTo).toHaveBeenCalledWith({ top: 320, behavior: 'auto' }))
  expect(host.querySelector('[data-question-uuid="q-1"]')?.getAttribute('aria-pressed')).toBe('true')
  expect(host.querySelector('.question-skeleton')).toBeNull()
})

it('uses the pre-rebuild status cells and retains metadata in the accessible name', async () => {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/selected-heatmap', component: HeatmapView }] })
  await router.push('/selected-heatmap')
  app = createApp(HeatmapView, { selectedOnly: true }); app.use(router).mount(host)
  await vi.waitFor(() => expect(host.querySelector('[data-question-uuid="q-1"]')).not.toBeNull())
  const cell = host.querySelector('[data-question-uuid="q-1"]')!
  expect(cell.classList.contains('status-review')).toBe(true)
  expect(cell.getAttribute('aria-label')).toContain('Question 1')
  expect(cell.querySelector('.cell-state-mark')).toBeNull()
  expect(cell.getAttribute('data-question-order')).toBe('1')
  expect(cell.childElementCount).toBe(0)
})

it('updates memoized cached cells and preview from a fresh server snapshot', async () => {
  const { cachedHeatmap } = await import('../lib/workspace')
  vi.mocked(cachedHeatmap).mockReturnValueOnce(payload)
  let resolve!: (value: unknown) => void
  vi.mocked(api).mockReturnValue(new Promise(done => { resolve = done }) as ReturnType<typeof api>)
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/selected-heatmap', component: HeatmapView }] })
  await router.push('/selected-heatmap?question=q-1')
  app = createApp(HeatmapView, { selectedOnly: true }); app.use(router).mount(host)
  await vi.waitFor(() => expect(host.querySelector('[data-question-uuid="q-1"]')?.getAttribute('aria-pressed')).toBe('true'))
  resolve({ ...payload, groups: [{ ...payload.groups[0], questions: [{ ...question, state: 'mastered', attempt_count: 2 }] }] })
  await vi.waitFor(() => expect(host.querySelector('[data-question-uuid="q-1"]')?.classList.contains('status-mastered')).toBe(true))
  const cell = host.querySelector('[data-question-uuid="q-1"]')!
  expect(cell.classList.contains('status-review')).toBe(false)
  expect(cell.getAttribute('aria-pressed')).toBe('true')
  expect(cell.getAttribute('aria-label')).toContain('2')
})


it('restores the historical total-first overview and locator beside the state filters', async () => {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/selected-heatmap', component: HeatmapView }] })
  await router.push('/selected-heatmap')
  app = createApp(HeatmapView, { selectedOnly: true }); app.use(router).mount(host)
  await vi.waitFor(() => expect(host.querySelector('.heatmap-overview strong')?.textContent).toBe('1'))
  expect(host.querySelector('.heatmap-overview')?.firstElementChild?.tagName).toBe('STRONG')
  expect(host.querySelector('.heatmap-overview .heatmap-next')).toBeNull()
  expect(host.querySelector('.heatmap-actions .heatmap-state-filters')).not.toBeNull()
  expect(host.querySelector('.heatmap-actions > .heatmap-next')).not.toBeNull()
})

it('loads remembered small questions immediately without fetching an unfiltered heatmap',async()=>{
 await accountPreferences.bind('browse-heatmap',{schema_version:1,revision:0,values:{...preferenceDefaults(),'browse.drill.filters':{type_group:'small'}},field_revisions:{}})
 const router=createRouter({history:createMemoryHistory(),routes:[{path:'/selected-heatmap',component:HeatmapView}]})
 await router.push('/selected-heatmap');app=createApp(HeatmapView,{selectedOnly:true});app.use(router).mount(host)
 await vi.waitFor(()=>expect(host.querySelector('[data-question-uuid="q-1"]')).not.toBeNull())
 expect(vi.mocked(api).mock.calls).toHaveLength(1)
 expect(String(vi.mocked(api).mock.calls[0]?.[0])).toContain('type_group=small')
 expect(host.querySelector<HTMLSelectElement>('.exam-type-toolbar select')?.value).toBe('small')
})
