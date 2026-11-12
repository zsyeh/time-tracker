// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import InsightView from './InsightView.vue'
import { api } from '../lib/api'
import { uiLanguage } from '../lib/uiPreferences'

const navigation = vi.hoisted(() => ({
  query: {} as Record<string, string>,
  push: vi.fn(),
  replace: vi.fn(),
}))
vi.mock('vue-router', () => ({ useRoute: () => ({ query: navigation.query }), useRouter: () => navigation }))
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
  sessionStorage.clear()
  uiLanguage.value = 'en'
  navigation.query = { q: 'old query', state: 'review', questions_page: '2' }
  navigation.replace.mockImplementation(async ({ query }: { query: Record<string, string> }) => { navigation.query = query })
  vi.mocked(api).mockResolvedValue(payload())
})
afterEach(() => { app?.unmount(); host?.remove(); app = undefined })

it('keeps advanced filters available while showing the main search and status first', async () => {
  await mount()
  expect(host.querySelector('.filter-primary')?.textContent).toContain('Keyword')
  expect(host.querySelector('.filter-primary')?.textContent).toContain('Question status')
  expect(host.querySelectorAll('.filter-dates input[type="date"]')).toHaveLength(2)
  expect(host.querySelectorAll('.filter-dates-mobile input[type="date"]')).toHaveLength(2)
  expect(host.querySelector('.filter-dates-mobile')?.hasAttribute('open')).toBe(false)
  expect(host.querySelector('#insight-advanced-filters')).toBeNull()
  host.querySelector<HTMLButtonElement>('.filter-more')!.click()
  await nextTick()
  expect(host.querySelectorAll('#insight-advanced-filters select')).toHaveLength(6)
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
  expect(sessionStorage.getItem('drill.insight.list.v1')).toBe('notes')
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
  expect(scrollTo).toHaveBeenCalledWith({ top: 320 })
  expect(sessionStorage.getItem('drill.insight.scroll.v1')).toBeNull()
  expect(host.querySelector('#insight-notes-tab')?.getAttribute('aria-selected')).toBe('true')
  scrollTo.mockRestore()
})
