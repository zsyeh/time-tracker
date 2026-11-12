// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import PdfPageStatusPanel from './PdfPageStatusPanel.vue'
import { api, post } from '../lib/api'
vi.mock('../lib/api', () => ({ api: vi.fn(), post: vi.fn() }))
let app: App | undefined
let host: HTMLDivElement
afterEach(() => { app?.unmount(); app = undefined; host?.remove(); vi.clearAllMocks() })
it('uses the same diagnosis selector while retaining batch preview payload and manual primary selection', async () => {
 vi.mocked(api).mockResolvedValue({ courses: [{ code: 'signal', label: 'Signals', question_max_page: 100, paired_max_page: 100 }] })
 vi.mocked(post).mockResolvedValue({ action: 'preview', course_label: 'Signals', result: 'review', matched_count: 0, created_count: 0, unmatched_question_pages: [], unmatched_paired_pages: [], stale_mapping_count: 0, questions: [] })
 host = document.createElement('div'); document.body.append(host); app = createApp(PdfPageStatusPanel); app.component('RouterLink', { template: '<a><slot /></a>' }); app.mount(host); await nextTick(); await nextTick()
 const pages = host.querySelector<HTMLInputElement>('.page-status-form > label input')!; pages.value = '12'; pages.dispatchEvent(new Event('input', { bubbles: true }))
 const review = host.querySelector<HTMLInputElement>('input[type=radio][value=review]')!; review.checked = true; review.dispatchEvent(new Event('change', { bubbles: true })); await nextTick()
 const codes = host.querySelectorAll<HTMLInputElement>('.diagnosis-selector input[type=checkbox]')
 expect(codes).toHaveLength(8)
 codes[0]!.checked = true; codes[0]!.dispatchEvent(new Event('change', { bubbles: true })); await nextTick()
 codes[1]!.checked = true; codes[1]!.dispatchEvent(new Event('change', { bubbles: true })); await nextTick()
 const primary = host.querySelector<HTMLSelectElement>('.primary-error select')!; primary.value = 'B1'; primary.dispatchEvent(new Event('change', { bubbles: true })); await nextTick()
 host.querySelector<HTMLButtonElement>('.preview-button')!.click(); await nextTick(); await nextTick()
 expect(post).toHaveBeenCalledWith('/api/drill/pdf-page-status/', expect.objectContaining({ action: 'preview', course: 'signal', question_pages: '12', result: 'review', error_codes: ['A', 'B1'], primary_error: 'B1', is_independent: true }))
 expect(vi.mocked(post).mock.calls.every((call) => (call[1] as { action: string }).action === 'preview')).toBe(true)
})
