// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import PracticeView from './PracticeView.vue'
import { api, ApiError } from '../lib/api'
import { cachedCatalog, cachedQuestionPage, prefetchQuestion } from '../lib/workspace'
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
 const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/practice', component: PracticeView }, { path: '/practice/:uuid', component: { template: '<div />' } }, { path: '/progress', component: { template: '<div />' } }, { path: '/preview', component: { template: '<div />' } }] })
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
 host.querySelector<HTMLButtonElement>('[data-page-position=bottom] .page-next')!.click()
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


it('shows the cached result page immediately while revalidating after returning', async () => {
 const cached = { count: 1, results: [{ ...question, display_label: 'Restored result' }], search: { version: 2, index_version: 'old:23' } }
 vi.mocked(cachedQuestionPage).mockReturnValueOnce(cached as never)
 vi.mocked(api).mockImplementationOnce(() => new Promise(() => {}))
 await mount('/practice?q=导数')
 expect(host.textContent).toContain('Restored result')
 expect(cachedQuestionPage).toHaveBeenCalledWith('q=%E5%AF%BC%E6%95%B0&search_version=2')
 expect(host.querySelector('.question-row')).not.toBeNull()
})

it('cancels a scheduled old-result prefetch as soon as the search draft changes', async () => {
 await mount('/practice?q=old')
 const input = host.querySelector<HTMLInputElement>('#practice-search')!
 input.value = 'new'; input.dispatchEvent(new Event('input', { bubbles: true }))
 await nextTick()
 await new Promise(resolve => setTimeout(resolve, 330)); await flush()
 expect(prefetchQuestion).not.toHaveBeenCalled()
})

it('reuses the same result and scroll cache key with the protocol flag added on return', async () => {
 const cached = { count: 1, results: [{ ...question, display_label: 'Returned result' }], search: { version: 2, index_version: 'old:23' } }
 vi.mocked(cachedQuestionPage).mockReturnValueOnce(cached as never)
 vi.mocked(api).mockImplementationOnce(() => new Promise(() => {}))
 await mount('/practice?q=导数&search_version=2&index_version=old%3A23')
 expect(host.textContent).toContain('Returned result')
 expect(cachedQuestionPage).toHaveBeenCalledWith('q=%E5%AF%BC%E6%95%B0&search_version=2')
})

it('applying a saved query discards a pending input draft even when the applied keyword is unchanged', async () => {
 const { bindTestPreferences, clearTestPreferences } = await import('../../../shared/preferences/testSupport')
 const { accountPreferences } = await import('../../../shared/preferences/store')
 await bindTestPreferences('en', 'preset-race')
 accountPreferences.set('filters.drill', [{ id: 'derivative', name: 'Saved derivative', query: { q: '导数' } }])
 try {
  const router = await mount('/practice?q=导数&from=circuit-selected')
  const input = host.querySelector<HTMLInputElement>('#practice-search')!
  input.value = 'pending draft'; input.dispatchEvent(new Event('input', { bubbles: true })); await nextTick()
  host.querySelector<HTMLButtonElement>('.saved-filter-entry > button')!.click(); await flush()
  document.querySelector<HTMLButtonElement>('.preset-open')!.click(); await flush()
  await new Promise(resolve => setTimeout(resolve, 320)); await flush()
  expect(router.currentRoute.value.query.q).toBe('导数')
  expect(router.currentRoute.value.query.from).toBeUndefined()
  expect(input.value).toBe('导数')
 } finally { clearTestPreferences() }
})


it('provides total pages and any-page jumps while preserving applied query and discarding an unsubmitted draft', async () => {
 vi.mocked(api).mockResolvedValue({count:97,page:1,page_size:24,total_pages:5,results:[question],previous:null,next:'next',search:{index_version:'fixture:2'}})
 const router=await mount('/practice?collection=selected&status=review&q=导数&sort=source&from=selected-heatmap')
 expect(host.querySelectorAll('.practice-pagination')).toHaveLength(2)
 expect(host.querySelector('.page-summary')!.textContent).toContain('1 / 5')
 const search=host.querySelector<HTMLInputElement>('#practice-search')!
 search.value='unsubmitted';search.dispatchEvent(new Event('input',{bubbles:true}));await nextTick()
 const jump=host.querySelector<HTMLInputElement>('[data-page-position=bottom] .page-jump input')!
 jump.value='4';jump.dispatchEvent(new Event('input'))
 host.querySelector('[data-page-position=bottom] form')!.dispatchEvent(new Event('submit',{cancelable:true}))
 await flush();await new Promise(resolve=>setTimeout(resolve,290));await flush()
 expect(router.currentRoute.value.query).toMatchObject({page:'4',collection:'selected',status:'review',q:'导数',sort:'source',from:'selected-heatmap',index_version:'fixture:2'})
 expect(search.value).toBe('导数')
 expect(String(vi.mocked(api).mock.calls.at(-1)![0])).not.toContain('unsubmitted')
})

it('uses the fixed legacy 24-item page contract for cached responses without pagination metadata', async () => {
 vi.mocked(api).mockResolvedValue({count:49,results:[question],previous:null,next:'next'})
 await mount('/practice')
 expect(host.querySelector('.page-summary')!.textContent).toContain('1 / 3')
})

it('opens one full Practice context without losing the original source return URL or current filters', async () => {
 const router=await mount('/practice?q=导数&status=review&collection=selected&page=2&index_version=v1&from=selected-heatmap&sort=source')
 const returnTo=router.currentRoute.value.fullPath
 host.querySelector<HTMLButtonElement>('.preview-all')!.click();await flush()
 const route=router.currentRoute.value
 expect(route.path).toBe('/preview')
 const context=JSON.parse(String(route.query.list))
 expect(context).toMatchObject({version:1,workspace:'drill',source:'practice',returnTo,query:{q:'导数',status:'review',collection:'selected',sort:'source'}})
 expect(context.query).not.toHaveProperty('page');expect(context.query).not.toHaveProperty('index_version');expect(context.query).not.toHaveProperty('from')
 expect(route.query.question).toBe('q-1')
})

it('keeps the bottom pagination anchor in the same viewport position after new-page data renders', async () => {
 vi.mocked(api).mockImplementation(async(url)=>({count:49,page:Number(new URL(String(url),'http://fixture').searchParams.get('page'))||1,page_size:24,total_pages:3,results:[{...question,uuid:String(url).includes('page=2')?'q-25':'q-1'}],next:'next',previous:'prev'}))
 await mount('/practice');vi.mocked(window.scrollTo).mockClear()
 vi.stubGlobal('scrollY',1000)
 Object.defineProperty(document.documentElement,'scrollHeight',{configurable:true,value:3000})
 const geometry=vi.spyOn(HTMLElement.prototype,'getBoundingClientRect').mockImplementation(function(this:HTMLElement){
  const top=this.dataset.pagePosition==='bottom'?(host.querySelector('[data-question-uuid=q-25]')?120:650):0
  return {top,bottom:top+44,left:0,right:100,width:100,height:44,x:0,y:top,toJSON(){}} as DOMRect
 })
 host.querySelector<HTMLButtonElement>('[data-page-position=bottom] .page-next')!.click();await flush()
 expect(window.scrollTo).toHaveBeenLastCalledWith({top:470,behavior:'auto'})
 geometry.mockRestore();delete (document.documentElement as unknown as Record<string,unknown>).scrollHeight
})

it('does not override a user scroll while pagination is awaiting its response', async () => {
 vi.mocked(api).mockResolvedValue({count:49,page_size:24,total_pages:3,results:[question],next:'next',previous:null})
 await mount('/practice');vi.mocked(window.scrollTo).mockClear()
 let resolve!:(value:unknown)=>void
 vi.mocked(api).mockImplementationOnce(()=>new Promise(finish=>{resolve=finish}))
 host.querySelector<HTMLButtonElement>('[data-page-position=bottom] .page-next')!.click();await flush()
 window.dispatchEvent(new Event('wheel'))
 resolve({count:49,page_size:24,total_pages:3,results:[{...question,uuid:'q-25'}],next:'next',previous:'prev'})
 await flush()
 expect(window.scrollTo).not.toHaveBeenCalled()
})

it('restores a cached question-row anchor immediately without waiting for revalidation', async () => {
 const key='q=%E5%AF%BC%E6%95%B0'
 sessionStorage.setItem('learning.practice.view.v2.drill.session.'+key,JSON.stringify({query:{q:'导数'},rowUuid:'q-1',rowOffset:120,scrollY:500,lastQuestionUuid:'q-1'}))
 vi.mocked(cachedQuestionPage).mockReturnValueOnce({count:1,results:[question],next:null,previous:null} as never)
 vi.mocked(api).mockImplementationOnce(()=>new Promise(()=>{}))
 vi.stubGlobal('scrollY',200)
 Object.defineProperty(document.documentElement,'scrollHeight',{configurable:true,value:3000})
 const geometry=vi.spyOn(HTMLElement.prototype,'getBoundingClientRect').mockImplementation(function(this:HTMLElement){
  const top=this.dataset.questionUuid==='q-1'?350:0
  return {top,bottom:top+44,left:0,right:100,width:100,height:44,x:0,y:top,toJSON(){}} as DOMRect
 })
 try{
  await mount('/practice?q=导数')
  expect(host.textContent).toContain('Derivative')
  expect(window.scrollTo).toHaveBeenLastCalledWith({top:430,behavior:'auto'})
 }finally{geometry.mockRestore();delete (document.documentElement as unknown as Record<string,unknown>).scrollHeight}
})

it('pins pagination to the restored cached generation when a pending search draft is discarded', async () => {
 const cached={count:49,results:[question],next:'next',previous:null,search:{index_version:'cache:7'}}
 vi.mocked(cachedQuestionPage).mockReturnValueOnce(cached as never)
 vi.mocked(api).mockResolvedValue(cached).mockImplementationOnce(()=>new Promise(()=>{}))
 const router=await mount('/practice?q=导数')
 const input=host.querySelector<HTMLInputElement>('#practice-search')!
 input.value='unsent';input.dispatchEvent(new Event('input',{bubbles:true}));await nextTick()
 host.querySelector<HTMLButtonElement>('[data-page-position=bottom] .page-next')!.click();await flush()
 expect(router.currentRoute.value.query).toMatchObject({q:'导数',page:'2',index_version:'cache:7'})
})
