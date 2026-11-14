// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App, type Component } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import CircuitSelectedView from './CircuitSelectedView.vue'
import SignalSelectedView from './SignalSelectedView.vue'
import AnalogSelectedView from './AnalogSelectedView.vue'
import DigitalSelectedView from './DigitalSelectedView.vue'
import CommunicationSelectedView from './CommunicationSelectedView.vue'
import { api } from '../lib/api'
import { accountPreferences } from '../../../shared/preferences/store'
import { preferenceDefaults } from '../../../shared/preferences/schema'
vi.mock('../lib/api', () => ({ api: vi.fn() }))
vi.mock('../components/ExamTypeControls.vue', () => ({ default: { template: '<div />' } }))
vi.mock('../components/HeatmapProgress.vue', () => ({ default: { template: '<div />' } }))
const item = { uuid: 'q-1', question_type: 'large', type_group: 'large', label: 'Original question 1', book: 'Book A', tier: 'advanced', bucket: 'test', kind: 'calculation', state: 'mastered', ready: true, combined: false, question_mode: 'image', answer_mode: 'image', scope_note: '', has_open_erratum: false, pdf_pages: null, tags: [], reason: ['Existing selection'] }
const progress = { total: 2, attempted: 1, mastered: 1, unattempted: 1 }
const payload = { title: 'Selected', basis: '', progress, ready_count: 2, inventory_count: 2, selected_count: 2, review_count: 0, excluded_count: 0, review_items: [], groups: [{ key: 'test', title: 'Test group', rank: 1, tier: 'advanced', focus: 'Original focus', progress, questions: [item, { ...item, uuid: 'q-2', label: 'Original question 2', state: 'unattempted' }] }] }
let app: App | undefined
let host: HTMLDivElement
beforeEach(async () => { await accountPreferences.bind('selected-owner',{schema_version:1,revision:0,values:preferenceDefaults(),field_revisions:{}}); vi.clearAllMocks(); host = document.createElement('div'); document.body.append(host); vi.mocked(api).mockResolvedValue(payload) })
afterEach(() => { app?.unmount(); accountPreferences.reset(true); accountPreferences.dispose(); app = undefined; host.remove() })
async function settle() { await nextTick(); await Promise.resolve(); await nextTick(); await new Promise(resolve => setTimeout(resolve, 0)) }
const cases: Array<[string, Component]> = [['circuit', CircuitSelectedView], ['signal', SignalSelectedView], ['analog', AnalogSelectedView], ['digital', DigitalSelectedView], ['communication', CommunicationSelectedView]]
it.each(cases)('%s keeps the collection filters, source order, labeled/matrix modes and direct start', async (kind, component) => {
 const path = `/${kind}-selected`
 const router = createRouter({ history: createMemoryHistory(), routes: [{ path, component }, { path: '/practice/:uuid', component: { template: '<div />' } }] })
 await router.push(`${path}?all=1&tier=advanced&bucket=test&state=review`); await router.isReady()
 app = createApp(component); app.use(router).mount(host); await settle()
 expect(String(vi.mocked(api).mock.calls[0]?.[0])).toContain(`/${kind}-selected/`)
 const grid = host.querySelector('.selected-question-grid')!
 expect([...grid.querySelectorAll('strong')].map((row) => row.textContent)).toEqual(['Original question 1', 'Original question 2'])
 expect(grid.querySelectorAll('.selected-state')).toHaveLength(2)
 const toggle = host.querySelector<HTMLInputElement>('.selected-legend input')!
 toggle.checked = false; toggle.dispatchEvent(new Event('change', { bubbles: true })); await nextTick()
 expect(grid.classList.contains('compact')).toBe(true)
 expect(grid.querySelectorAll('button')).toHaveLength(2)
 host.querySelector<HTMLButtonElement>('.primary-action')!.click(); await settle()
 expect(router.currentRoute.value.path).toBe('/practice/q-2')
 expect(router.currentRoute.value.query).toMatchObject({ collection: `${kind}_selected`, from: `${kind}-selected`, tier: 'advanced', bucket: 'test', state: 'review' })
})
