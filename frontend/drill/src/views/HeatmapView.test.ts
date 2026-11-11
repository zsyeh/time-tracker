// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import HeatmapView from './HeatmapView.vue'
import { api } from '../lib/api'
import { uiLanguage } from '../lib/uiPreferences'

vi.mock('../lib/api', () => ({ api: vi.fn(), post: vi.fn(), remove: vi.fn() }))
vi.mock('../components/LearningSharePanel.vue', () => ({ default: { template: '<div />' } }))

let app: App | undefined
let host: HTMLDivElement
afterEach(() => {
  app?.unmount()
  host?.remove()
  sessionStorage.clear()
  uiLanguage.value = 'en'
  vi.resetAllMocks()
})

const payload = {
  question_count: 1,
  topic_count: 1,
  statistics: {
    attempted_question_count: 0, mastered_question_count: 0, review_question_count: 0,
    master_rate_percent: null, timed_attempt_count: 0, average_time_seconds: null,
    mastered_average_time_seconds: null, review_average_time_seconds: null,
  },
  groups: [{
    document_id: 7, document: 'Book A',
    questions: [{
      uuid: 'question-a', order: 1, label: 'Problem 1', topic: 'Chapter 1', year: 2020,
      variant: '', attempt_count: 0, latest_result: null, review_overdue: false, state: 'unattempted' as const,
      source_indexed: false, type_group: 'small',
    }],
    topics: [{
      topic_id: 3, topic: 'Limits', path: 'Chapter 1 / Limits', question_count: 1,
      attempted_question_count: 0, mastered_question_count: 0, review_question_count: 0,
      attempt_count: 0, coverage_percent: 0, intensity: 0 as const, state: 'unattempted' as const,
    }],
    statistics: {
      attempted_question_count: 0, mastered_question_count: 0, review_question_count: 0,
      coverage_percent: 0, master_rate_percent: null, timed_attempt_count: 0,
      average_time_seconds: null, mastered_average_time_seconds: null, review_average_time_seconds: null,
    },
  }],
}

async function flush() { await new Promise((resolve) => setTimeout(resolve, 0)); await nextTick() }

async function mountHeatmap(path = '/heatmap?scope=all') {
  window.scrollTo = vi.fn()
  const router = createRouter({ history: createMemoryHistory(), routes: [
    { path: '/heatmap', component: HeatmapView },
    { path: '/selected-heatmap', component: HeatmapView, props: { selectedOnly: true } },
    { path: '/practice/:uuid', component: { template: '<div />' } },
    { path: '/practice', component: { template: '<div />' } },
  ] })
  await router.push(path)
  await router.isReady()
  host = document.createElement('div')
  document.body.append(host)
  app = createApp({ template: '<router-view />' })
  app.use(router)
  app.mount(host)
  await flush()
  return router
}

describe('Heatmap view', () => {
  it('keeps status labels visible and preserves preview-to-question navigation', async () => {
    vi.mocked(api).mockResolvedValue(payload)
    const router = await mountHeatmap()

    expect(host.querySelector('.heat-legend')?.textContent).toContain('Not started')
    expect(host.querySelector('.heat-legend')?.textContent).toContain('Overdue')
    host.querySelector<HTMLButtonElement>('[data-question-uuid="question-a"]')!.click()
    await nextTick()
    expect(host.querySelector('.question-preview-card h3')?.textContent).toBe('Problem 1')
    host.querySelector<HTMLButtonElement>('.question-preview-card .topic-preview-open')!.click()
    await flush()
    expect(router.currentRoute.value.path).toBe('/practice/question-a')
    expect(router.currentRoute.value.query).toMatchObject({ from: 'heatmap', heat_scope: 'all', heat_question: 'question-a', document: '7' })
  })

  it('keeps source scope filtering in the API request', async () => {
    vi.mocked(api).mockResolvedValue(payload)
    await mountHeatmap()
    host.querySelector<HTMLButtonElement>('.heat-scope button:nth-child(2)')!.click()
    await flush()
    expect(api).toHaveBeenLastCalledWith(expect.stringContaining('scope=past_exam'))
  })

  it('keeps the selected question matrix ahead of optional timing details', async () => {
    vi.mocked(api).mockResolvedValue(payload)
    await mountHeatmap('/selected-heatmap')

    expect(host.querySelector('.selected-heatmap-page .question-heatmap')).not.toBeNull()
    expect(host.querySelector('.heatmap-summary')?.hasAttribute('open')).toBe(false)
    expect(host.querySelector('.heatmap-group .heatmap-progress')).toBeNull()
    expect(host.querySelector('.heatmap-book-progress[role="progressbar"]')).not.toBeNull()
  })
})
