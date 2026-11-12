// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import EiCockpitView from './EiCockpitView.vue'
import { api } from '../lib/api'
vi.mock('../lib/api', () => ({ api: vi.fn() }))
const topic = { id: 1, chapter: 'Chapter', title: 'Long knowledge point title', requirement: 'master', requirement_excerpt: 'Official requirement', grade: 'A', attempts: 4, accuracy: 75, average_time_seconds: 120, last_reviewed_at: null, next_review_at: null, due: true, correct_streak: 1, retention_score: 60, representative_question_uuid: 'q-1' }
const payload = { exam_overview: { source: 'Official', compiled_at: '2026-11-12', duration_minutes: 180, total_score: 150, course_weight: 'Five subjects', question_structure: [] }, coverage_percent: 50, counts: { A: 1, B: 0, C: 0, D: 0 }, due_count: 1, courses: [{ code: 'circuit', label: 'Circuit', coverage_percent: 50, counts: { A: 1, B: 0, C: 0, D: 0 }, topics: [topic], official_syllabus: [] }], recommendations: [{ ...topic, course: 'Circuit', reason: 'Long actionable recommendation '.repeat(5), priority: 1 }], type_stats: [], diagnosis: { largest_gap: 'Gap', allocation: 'Allocation', next_focus: 'Next focus' }, requirement_notice: 'Original notice' }
let app: App | undefined
let host: HTMLDivElement
beforeEach(() => { vi.clearAllMocks(); host = document.createElement('div'); document.body.append(host); vi.mocked(api).mockImplementation(async (_url, options) => options?.method === 'PATCH' ? { grade: 'B', next_review_at: null, retention_score: 60, correct_streak: 1 } as never : structuredClone(payload) as never) })
afterEach(() => { app?.unmount(); app = undefined; host.remove() })
async function settle() { await nextTick(); await Promise.resolve(); await nextTick(); await new Promise(resolve => setTimeout(resolve, 0)) }
it('keeps one-click A/B/C/D saving and exposes selection and disclosure state', async () => {
 const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/cockpit', component: EiCockpitView }, { path: '/practice', component: { template: '<div />' } }, { path: '/practice/:uuid', component: { template: '<div />' } }] }); await router.push('/cockpit'); await router.isReady()
 app = createApp(EiCockpitView); app.use(router).mount(host); await settle()
 expect(host.querySelector('.course-toggle')?.getAttribute('aria-expanded')).toBe('true')
 const grades = host.querySelectorAll<HTMLButtonElement>('.grade-switch button')
 expect(grades).toHaveLength(4); expect(grades[0]?.getAttribute('aria-pressed')).toBe('true')
 grades[1]!.click(); await settle()
 expect(vi.mocked(api).mock.calls.find((call) => call[1]?.method === 'PATCH')).toEqual(['/api/drill/cockpit/topics/1/', { method: 'PATCH', body: JSON.stringify({ grade: 'B', reviewed: true }) }])
 expect(host.querySelector('.cockpit-recommend')?.textContent).toContain('Long actionable recommendation')
 expect(host.querySelector('.topic-due')).not.toBeNull()
})
