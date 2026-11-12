// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import PracticeView from './PracticeView.vue'
import { api, ApiError } from '../lib/api'
import { cachedCatalog } from '../lib/workspace'
vi.mock('../lib/api', () => ({ api: vi.fn(), ApiError: class extends Error { constructor(public status: number, message: string) { super(message) } } }))
vi.mock('../lib/workspace', () => ({ cachedCatalog: vi.fn(), cachedQuestionPage: vi.fn(() => null), fetchCatalog: vi.fn(async () => catalog), prefetchQuestion: vi.fn(), storeQuestionPage: vi.fn() }))
const catalog = { summary: { imported_count: 2, practiceable_count: 2, outline_count: 0, categories: [] }, coverage: { available: [], missing: [], source_archive_checked: false }, documents: [{ id: 1, title: 'Book', question_count: 2 }], topics: [] }
const question = { uuid: 'q-1', question_order: 1, display_label: 'Derivative', document: 'Book', topic: 'Calculus', source_category_label: 'Workbook', state: 'unattempted', attempt_count: 0 }
let app: App | undefined
let host: HTMLDivElement
beforeEach(() => { vi.clearAllMocks(); sessionStorage.clear(); localStorage.clear(); host = document.createElement('div'); document.body.append(host); vi.mocked(cachedCatalog).mockReturnValue(catalog as never); vi.stubGlobal('scrollTo', vi.fn()); vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => { callback(0); return 1 }); vi.mocked(api).mockResolvedValue({ count: 1, results: [question], previous: null, next: null }) })
afterEach(() => { app?.unmount(); app = undefined; host.remove(); vi.unstubAllGlobals(); vi.useRealTimers() })
async function flush() { await nextTick(); await Promise.resolve(); await nextTick(); await new Promise(resolve => setTimeout(resolve, 0)) }
async function mount(url: string) {
 const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/practice', component: PracticeView }, { path: '/practice/:uuid', component: { template: '<div />' } }, { path: '/progress', component: { template: '<div />' } }] })
 await router.push(url); await router.isReady(); app = createApp(PracticeView); app.use(router).mount(host); await flush(); return router
}
it('preserves explicit URL filters and page when entering a question', async () => {
 const router = await mount('/practice?collection=math2_selected&status=review&q=导&page=3&sort=source')
 expect(String(vi.mocked(api).mock.calls[0]?.[0])).toContain('q=%E5%AF%BC')
 host.querySelector<HTMLAnchorElement>('.question-row')!.click(); await flush()
 expect(router.currentRoute.value.path).toBe('/practice/q-1')
 expect(router.currentRoute.value.query).toMatchObject({ collection: 'math2_selected', status: 'review', q: '导', practice_page: '3', sort: 'source' })
})
it('keeps collection scope and keyword when clearing ordinary filters', async () => {
 const router = await mount('/practice?collection=math2_selected&q=导数&document=1&favorite=1')
 host.querySelector<HTMLButtonElement>('.filter-summary button')!.click(); await flush()
 expect(router.currentRoute.value.query).toEqual({ collection: 'math2_selected', q: '导数' })
})
it('does not let an old response replace the current query during debounce', async () => {
 let finishOld!: (value: unknown) => void
 vi.mocked(api).mockImplementationOnce(() => new Promise(resolve => { finishOld = resolve }))
 await mount('/practice?q=old')
 const input = host.querySelector<HTMLInputElement>('#practice-search')!
 input.value = 'new'; input.dispatchEvent(new Event('input', { bubbles: true })); await nextTick()
 finishOld({ count: 1, results: [{ ...question, display_label: 'Stale title' }] }); await flush()
 expect(host.textContent).not.toContain('Stale title')
 await new Promise(resolve => setTimeout(resolve, 280)); await flush()
 expect(String(vi.mocked(api).mock.calls.at(-1)?.[0])).toContain('q=new')
 expect(host.textContent).toContain('Derivative')
})

it('pins pagination to the search index and reports a 409 refresh without losing filters', async () => {
 const first = { count: 40, results: [question], previous: null, next: 'next', search: { version: 2, index_version: 'fixture:1' } }
 vi.mocked(api).mockResolvedValue(first)
 const router = await mount('/practice?q=导数&status=review')
 vi.mocked(api).mockRejectedValueOnce(new ApiError(409, 'Index changed'))
 host.querySelector<HTMLButtonElement>('.pager button:last-child')!.click()
 await vi.waitFor(() => expect(vi.mocked(api).mock.calls.some((call) => String(call[0]).includes('index_version=fixture%3A1'))).toBe(true))
 await vi.waitFor(() => expect(router.currentRoute.value.query.page).toBeUndefined())
 expect(router.currentRoute.value.query).toMatchObject({ q: '导数', status: 'review' })
 expect(host.querySelector('.search-notice')?.textContent).toContain('1')
 expect(String(vi.mocked(api).mock.calls.at(-1)?.[0])).not.toContain('index_version=')
})

it('renders only public search excerpts as safe text and highlights Unicode codepoint ranges', async () => {
 const excerpt = '𝑥 <script>not HTML</script> 偏导数'
 const points = Array.from(excerpt)
 const index = points.indexOf('偏')
 vi.mocked(api).mockResolvedValue({ count: 1, results: [{ ...question, search_match: { fields: ['topic'], kind: 'literal', excerpt, highlights: [[0, 1], [index, index + 3]], coverage: 'metadata' } }], previous: null, next: null })
 await mount('/practice?q=偏导数')
 const summary = host.querySelector('.practice-search-excerpt')!
 expect(summary.textContent).toContain('<script>not HTML</script>')
 expect(summary.querySelector('script')).toBeNull()
 expect([...summary.querySelectorAll('mark')].map((mark) => mark.textContent)).toEqual(['𝑥', '偏导数'])
 expect(summary.querySelector('.search-match-label')).not.toBeNull()
})

it('explains spelling expansion without replacing the original query', async () => {
 vi.mocked(api).mockResolvedValue({ count: 1, results: [question], search: { corrected_terms: ['fourier'] } })
 const router = await mount('/practice?q=Fourrier')
 expect(host.querySelector('.search-expansion')?.textContent).toContain('fourier')
 expect(host.querySelector<HTMLInputElement>('#practice-search')?.value).toBe('Fourrier')
 expect(router.currentRoute.value.query.q).toBe('Fourrier')
})
