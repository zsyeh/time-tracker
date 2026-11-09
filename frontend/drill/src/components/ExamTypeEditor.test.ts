// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import ExamTypeEditor from './ExamTypeEditor.vue'
import { api } from '../lib/api'
import { uiLanguage } from '../lib/uiPreferences'
import type { QuestionDetail } from '../types'
vi.mock('../lib/api', () => ({ api: vi.fn() }))
let app: App | undefined
let host: HTMLDivElement
const flush = async () => { await new Promise((resolve) => setTimeout(resolve, 0)); await nextTick() }
afterEach(() => { app?.unmount(); host?.remove(); vi.resetAllMocks() })
async function mount() {
  uiLanguage.value = 'en'
  host = document.createElement('div'); document.body.append(host)
  const saved = vi.fn()
  app = createApp(ExamTypeEditor, { question: { uuid: 'q1', question_type: 'choice', type_group: 'small' } as QuestionDetail, onSaved: saved })
  app.mount(host); await flush()
  return saved
}
it('fetches revision on opening and saves only after explicit selection and save', async () => {
  vi.mocked(api).mockResolvedValueOnce({ question_type: 'choice', classification: { updated_at: 'revision1' } })
    .mockResolvedValueOnce({ question_type: 'fill', type_group: 'small' })
  const saved = await mount()
  expect(host.querySelector('select')).toBeNull()
  expect(api).not.toHaveBeenCalled()
  host.querySelector('button')!.click(); await flush()
  const select = host.querySelector('select')!
  select.value = 'fill'; select.dispatchEvent(new Event('change')); await flush()
  expect(api).toHaveBeenCalledTimes(1)
  const save = [...host.querySelectorAll('button')].find((b) => b.textContent === 'Save')!
  save.click(); await flush()
  expect(api).toHaveBeenLastCalledWith('/api/drill/questions/q1/exam-type/', {
    method: 'PATCH', body: JSON.stringify({ question_type: 'fill', expected_updated_at: 'revision1' }),
  })
  expect(saved).toHaveBeenCalledWith({ question_type: 'fill', type_group: 'small' })
  expect(host.querySelector('select')).toBeNull()
})
it('does not claim success or change the badge after a rejected save', async () => {
  vi.mocked(api).mockResolvedValueOnce({ question_type: 'choice', classification: { updated_at: 'r' } })
    .mockRejectedValueOnce(new Error('conflict'))
  const saved = await mount()
  host.querySelector('button')!.click(); await flush()
  ;[...host.querySelectorAll('button')].find((b) => b.textContent === 'Save')!.click(); await flush()
  expect(saved).not.toHaveBeenCalled()
  expect(host.querySelector('[role=alert]')?.textContent).toContain('Not saved')
  expect(host.querySelector('.format-trigger')?.textContent).toContain('Choice')
})
