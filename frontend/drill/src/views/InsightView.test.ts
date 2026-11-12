// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import InsightView from './InsightView.vue'
import { api } from '../lib/api'
import { uiLanguage } from '../lib/uiPreferences'
import { setLearningUser } from '../../../shared/foregroundTimer'

const navigation = vi.hoisted(() => ({
  query: {} as Record<string, string>,
  push: vi.fn(),
  replace: vi.fn(),
}))
vi.mock('vue-router', () => ({ useRoute: () => ({ get query() { return navigation.query }, get fullPath() { return '/insight?' + new URLSearchParams(navigation.query).toString() } }), useRouter: () => navigation }))
vi.mock('../lib/api', () => ({ api: vi.fn() }))
vi.mock('../components/LearningSharePanel.vue', () => ({ default: { template: '<div />' } }))

let app: App | undefined
let host: HTMLDivElement
const payload = () => ({
  marker_stats: [],
  recent_questions: { count: 21, page: 2, page_size: 10, total_pages: 3, previous_page: 1, next_page: 3, results: [
    { attempt_id: 1, uuid: 'attempt-1', label: 'Question 17', document: 'Book A', topic: 'Chapter 2', result: 'review', created_at: '2026-11-11T08:15:00Z', diagnoses: ['K1'], note_excerpt: 'Check the basis first' },
  ] },
  recent_notes: { count: 12, page: 1, page_size: 10, total_pages: 2, previous_page: null, next_page: 2, results: [
    { uuid: 'note-1', label: 'Question 29', document: 'Book B', topic: 'Chapter 3', note: 'Repeated note '.repeat(10), updated_at: '2026-11-10T06:00:00Z', result: 'review', primary_error: 'K2' },
  ] },
  options: { errors: [{ code: 'K1', label: 'Knowledge' }], courses: [{ code: 'math', label: 'Math' }], documents: [{ id: 1, label: 'Book A' }], topics: [{ id: 2, label: 'Chapter 2' }] },
})

async function settle() { await Promise.resolve(); await nextTick(); await nextTick() }
async function mount() {
  host = document.createElement('div')
  document.body.append(host)
  app = createApp(InsightView)
  app.mount(host)
  await settle()
}
beforeEach(() => {
  vi.clearAllMocks()
  setLearningUser('')
  sessionStorage.clear()
  uiLanguage.value = 'en'
  navigation.query = { q: 'old query', state: 'review', questions_page: '2' }
  navigation.replace.mockImplementation(async ({ query }: { query: Record<string, string> }) => { navigation.query = query })
  vi.mocked(api).mockResolvedValue(payload())
})
afterEach(() => { app?.unmount(); host?.remove(); app = undefined; vi.useRealTimers(); setLearningUser('') })

it('keeps advanced filters available while showing the main search and status first', async () => {
  await mount()
  expect(host.querySelector('.filter-primary')?.textContent).toContain('Keyword')
  expect(host.querySelector('.filter-primary')?.textContent).toContain('Question status')
  expect(host.querySelector('.filter-sort')).not.toBeNull()
  expect(host.querySelectorAll('.filter-dates input[type="date"]')).toHaveLength(2)
  expect(host.querySelectorAll('.filter-dates-mobile input[type="date"]')).toHaveLength(2)
  expect(host.querySelector('.filter-dates-mobile')?.hasAttribute('open')).toBe(false)
  expect(host.querySelector('#insight-advanced-filters')).toBeNull()
  host.querySelector<HTMLButtonElement>('.filter-more')!.click()
  await nextTick()
  expect(host.querySelectorAll('#insight-advanced-filters select')).toHaveLength(5)
  expect(host.querySelector('#insight-advanced-filters input[type="date"]')).toBeNull()
  expect(host.textContent).toContain('Repeated note')
  expect(host.textContent).toContain('K1')
  expect(host.querySelector('.record-note')?.textContent).toContain('Check the basis first')
})

it('keeps the date range in the applied URL and retains both page cursors', async () => {
  navigation.query = { q: 'old query', start: '2026-11-01', end: '2026-11-11', questions_page: '2', notes_page: '2' }
  await mount()
  expect(host.querySelector('.filter-dates-mobile')?.hasAttribute('open')).toBe(true)
  expect(host.querySelector('.filter-dates-mobile summary')?.textContent).toContain('2026-11-01 – 2026-11-11')
  expect(host.querySelector('#insight-advanced-filters')).toBeNull()
  const target = vi.mocked(api).mock.calls.at(-1)![0]
  expect(target).toContain('start=2026-11-01')
  expect(target).toContain('end=2026-11-11')
  expect(target).toContain('questions_page=2')
  expect(target).toContain('notes_page=2')
})

it('applies dates from the compact mobile date control without changing filter semantics', async () => {
  await mount()
  const compactDates = host.querySelector<HTMLDetailsElement>('.filter-dates-mobile')!
  compactDates.querySelector('summary')!.click()
  await settle()
  expect(compactDates.open).toBe(true)
  const start = compactDates.querySelector<HTMLInputElement>('input[type="date"]')!
  start.value = '2026-11-01'
  start.dispatchEvent(new Event('input'))
  await nextTick()
  host.querySelector<HTMLButtonElement>('.filter-submit')!.click()
  await settle()
  expect(vi.mocked(api).mock.calls.at(-1)![0]).toContain('start=2026-11-01')
  expect(navigation.query.start).toBe('2026-11-01')
})

it('keeps independent pages and returns to the applied query and saved list', async () => {
  await mount()
  const search = host.querySelector<HTMLInputElement>('input[type="search"]')!
  search.value = 'unapplied text'
  search.dispatchEvent(new Event('input'))
  await nextTick()
  host.querySelector<HTMLButtonElement>('#insight-notes-tab')!.click()
  host.querySelector<HTMLButtonElement>('#insight-notes article header button')!.click()
  const target = navigation.push.mock.calls.at(-1)![0]
  expect(target.path).toBe('/practice/note-1')
  expect(target.query.insight_return).toContain('questions_page=2')
  expect(target.query.insight_return).toContain('q=old+query')
  expect(target.query.insight_return).not.toContain('unapplied')
  expect(sessionStorage.getItem('drill.insight.v2.anonymous.list')).toBe('notes')
  const nextNotes = [...host.querySelectorAll<HTMLButtonElement>('#insight-notes .insight-pagination button')][1]!
  nextNotes.click()
  await settle()
  expect(vi.mocked(api).mock.calls.at(-1)![0]).toContain('notes_page=2')
  expect(vi.mocked(api).mock.calls.at(-1)![0]).toContain('questions_page=2')
})

it('restores scroll and the selected mobile list when returning from a question', async () => {
  sessionStorage.setItem('drill.insight.scroll.v1', '320')
  sessionStorage.setItem('drill.insight.list.v1', 'notes')
  const scrollTo = vi.spyOn(window, 'scrollTo').mockImplementation(() => {})
  await mount()
  await vi.waitFor(() => expect(scrollTo).toHaveBeenCalledWith({ top: 320 }))
  expect(sessionStorage.getItem('drill.insight.scroll.v1')).toBeNull()
  expect(host.querySelector('#insight-notes-tab')?.getAttribute('aria-selected')).toBe('true')
  scrollTo.mockRestore()
})

it('debounces keyword search for 250ms and does not send unfinished IME text', async () => {
  await mount()
  vi.useFakeTimers()
  const initial = vi.mocked(api).mock.calls.length
  const input = host.querySelector<HTMLInputElement>('input[type="search"]')!
  input.dispatchEvent(new CompositionEvent('compositionstart'))
  input.value = '偏'; input.dispatchEvent(new Event('input'))
  await vi.advanceTimersByTimeAsync(500)
  expect(api).toHaveBeenCalledTimes(initial)
  input.value = '偏导数'; input.dispatchEvent(new CompositionEvent('compositionend'))
  await vi.advanceTimersByTimeAsync(249)
  expect(api).toHaveBeenCalledTimes(initial)
  await vi.advanceTimersByTimeAsync(1)
  expect(api).toHaveBeenCalledTimes(initial + 1)
  expect(vi.mocked(api).mock.calls.at(-1)![0]).toContain('q=%E5%81%8F%E5%AF%BC%E6%95%B0')
  expect(vi.mocked(api).mock.calls.at(-1)![0]).not.toContain('questions_page=')
})

it('supersedes an old response during the debounce window without replacing newer results', async () => {
  let resolveFirst!: (value: ReturnType<typeof payload>) => void
  vi.mocked(api).mockReturnValueOnce(new Promise(done => { resolveFirst = done }) as ReturnType<typeof api>).mockResolvedValue(payload())
  await mount()
  const input = host.querySelector<HTMLInputElement>('input[type="search"]')!
  input.value = 'Fourier'; input.dispatchEvent(new Event('input'))
  expect((vi.mocked(api).mock.calls[0]![1]?.signal as AbortSignal).aborted).toBe(true)
  await new Promise(done => setTimeout(done, 270)); await settle()
  const stale = payload(); stale.recent_questions.results[0]!.label = 'Stale old result'
  resolveFirst(stale); await settle()
  expect(host.textContent).toContain('Question 17')
  expect(host.textContent).not.toContain('Stale old result')
})

it('keeps multiple Attempts for the same question and persists expanded Note state', async () => {
  const data = payload()
  data.recent_questions.results.push({ ...data.recent_questions.results[0]!, attempt_id: 2, created_at: '2026-11-10T08:15:00Z' })
  vi.mocked(api).mockResolvedValue(data)
  await mount()
  expect(host.querySelectorAll('#insight-attempts .insight-list > button')).toHaveLength(2)
  const expand = host.querySelector<HTMLButtonElement>('#insight-notes article footer button')!
  expand.click(); await nextTick()
  expect(expand.getAttribute('aria-expanded')).toBe('true')
  expect(host.querySelector('#note-body-note-1')?.classList.contains('expanded')).toBe(true)
  app!.unmount(); app = undefined; host.remove()
  await mount()
  expect(host.querySelector('#note-body-note-1')?.classList.contains('expanded')).toBe(true)
})

it('uses roving tab focus and retains separate pagination while switching mobile lists', async () => {
  await mount()
  const attempts = host.querySelector<HTMLButtonElement>('#insight-attempts-tab')!
  expect(attempts.tabIndex).toBe(0)
  attempts.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }))
  await nextTick()
  const notes = host.querySelector<HTMLButtonElement>('#insight-notes-tab')!
  expect(notes.tabIndex).toBe(0); expect(document.activeElement).toBe(notes)
  expect(attempts.tabIndex).toBe(-1)
  expect(navigation.query.questions_page).toBe('2')
})

it('does not restore another account or query scroll state', async () => {
  setLearningUser('account-2')
  sessionStorage.setItem('drill.insight.v2.account-1.scroll', JSON.stringify({ top: 500, query: '' }))
  sessionStorage.setItem('drill.insight.v2.account-2.scroll', JSON.stringify({ top: 600, query: 'q=other' }))
  const scroll = vi.spyOn(window, 'scrollTo').mockImplementation(() => {})
  await mount(); await new Promise(done => setTimeout(done, 50))
  expect(scroll).not.toHaveBeenCalled()
  scroll.mockRestore()
})

it('opens attempts preview from applied filters and the current attempt without committing an unsent search draft',async()=>{
 navigation.query={q:'old query',state:'review',start:'2026-11-01',end:'2026-11-11',questions_page:'2',notes_page:'2',sort:'oldest'}
 const response=payload();response.recent_notes.page=2;vi.mocked(api).mockResolvedValue(response)
 await mount()
 const input=host.querySelector<HTMLInputElement>('.filter-keyword input')||host.querySelector<HTMLInputElement>('input[type=search]')!
 input.value='unsubmitted note draft';input.dispatchEvent(new Event('input',{bubbles:true}));await nextTick()
 host.querySelector<HTMLButtonElement>('[data-preview-list=attempts]')!.click();await settle()
 const location=navigation.push.mock.calls.at(-1)![0]
 expect(location.path).toBe('/preview')
 const context=JSON.parse(location.query.list)
 expect(context.source).toBe('attempts')
 expect(context.query).toMatchObject({q:'old query',state:'review',start:'2026-11-01',end:'2026-11-11',sort:'oldest'})
 expect(context.returnTo).toContain('questions_page=2');expect(context.returnTo).toContain('notes_page=2')
 expect(context.query).not.toHaveProperty('questions_page');expect(context.query).not.toHaveProperty('notes_page')
 expect(context.query.q).not.toContain('unsubmitted')
 expect(location.query.entry).toBe('attempt:1');expect(location.query.question).toBe('attempt-1')
})
it('provides an independent notes preview context while retaining both history page cursors',async()=>{
 navigation.query={q:'saved note',has_note:'1',document:'1',questions_page:'3',notes_page:'2'}
 const response=payload();response.recent_questions.page=3;response.recent_notes.page=2;vi.mocked(api).mockResolvedValue(response)
 await mount()
 host.querySelector<HTMLButtonElement>('[data-preview-list=notes]')!.click();await settle()
 const location=navigation.push.mock.calls.at(-1)![0],context=JSON.parse(location.query.list)
 expect(context).toMatchObject({source:'notes',query:{q:'saved note',has_note:'1',document:'1'}})
 expect(context.returnTo).toContain('questions_page=3');expect(context.returnTo).toContain('notes_page=2')
 expect(location.query.question).toBe('note-1');expect(location.query.entry).toBeUndefined()
})
