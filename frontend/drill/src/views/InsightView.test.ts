// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import InsightView from './InsightView.vue'
import { api } from '../lib/api'
import { uiLanguage } from '../lib/uiPreferences'

vi.mock('../lib/api', () => ({ api: vi.fn(), post: vi.fn(), remove: vi.fn() }))
vi.mock('../components/LearningSharePanel.vue', () => ({ default: { template: '<div />' } }))
let app: App | undefined
let host: HTMLDivElement
afterEach(() => {
  app?.unmount()
  host?.remove()
  uiLanguage.value = 'en'
  vi.resetAllMocks()
})

const payload = {
  marker_stats: [],
  recent_questions: { count: 1, page: 1, page_size: 20, total_pages: 1, next_page: null, previous_page: null,
    results: [{ uuid: 'q-1', label: 'Problem 12', document: 'Book A', topic: 'Chapter 2', result: 'review', created_at: '2026-11-10T08:00:00Z', diagnoses: ['C1'] }] },
  recent_notes: { count: 1, page: 1, page_size: 20, total_pages: 1, next_page: null, previous_page: null,
    results: [{ uuid: 'q-2', label: 'Problem 13', document: 'Book B', topic: 'Chapter 3', note: 'Review this derivation', updated_at: '2026-11-10T09:00:00Z', result: 'correct', primary_error: null }] },
  options: { errors: [{ code: 'C1', label: 'Recall failure' }], courses: [], documents: [{ id: 2, label: 'Book B' }], topics: [{ id: 3, label: 'Chapter 3' }] },
}
async function flush() { await new Promise((resolve) => setTimeout(resolve, 0)); await nextTick() }
function mountHistory(path: string) {
  window.scrollTo = vi.fn()
  const router = createRouter({ history: createMemoryHistory(), routes: [
    { path: '/insight', component: InsightView }, { path: '/practice/:uuid', component: { template: '<div />' } },
  ] })
  return router.push(path).then(async () => {
    await router.isReady()
    host = document.createElement('div')
    document.body.append(host)
    app = createApp({ template: '<router-view />' })
    app.use(router)
    app.mount(host)
    await flush()
    return router
  })
}

describe('History view', () => {
  it('layers advanced filters while keeping filtering and question return state intact', async () => {
    vi.mocked(api).mockResolvedValue(payload)
    const router = await mountHistory('/insight?state=review&questions_page=2')

    expect(host.querySelector('.quick-filter-row')).not.toBeNull()
    expect(host.querySelector('.advanced-filters summary')?.textContent).toContain('More filters')
    expect((host.querySelector('select') as HTMLSelectElement).value).toBe('review')
    const advanced = host.querySelector('.advanced-filters') as HTMLDetailsElement
    advanced.open = true
    const book = [...host.querySelectorAll('select')].find((select) => select.closest('label')?.textContent?.includes('Book'))
    expect(book).toBeDefined()
    book!.value = '2'
    book!.dispatchEvent(new Event('change', { bubbles: true }))
    host.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    await flush()
    expect(api).toHaveBeenLastCalledWith('/api/drill/insight/?document=2&state=review&sort=recent')

    ;(host.querySelector('.attempts-column .insight-list > button') as HTMLButtonElement).click()
    await flush()
    expect(router.currentRoute.value.path).toBe('/practice/q-1')
    expect(router.currentRoute.value.query.insight_list).toBe('attempts')
    expect(router.currentRoute.value.query.insight_return).toBe('/insight?document=2&state=review&sort=recent')
  })

  it('shows attempts and notes as two columns on wide layouts with scannable status and dates', async () => {
    vi.mocked(api).mockResolvedValue(payload)
    await mountHistory('/insight')
    expect(host.querySelectorAll('.history-column')).toHaveLength(2)
    expect(host.querySelector('.attempts-column .history-meta em')?.textContent).toBe('Review')
    expect(host.querySelector('.note-list article > p')?.textContent).toContain('Review this derivation')
    expect(host.querySelector('.note-list article > footer button:last-child')?.textContent).toContain('Open question')
  })
})
