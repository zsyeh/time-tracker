// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import ExamTypeEditor from './ExamTypeEditor.vue'
import ExamTypeControls from './ExamTypeControls.vue'
import { api } from '../lib/api'
import { uiLanguage } from '../lib/uiPreferences'
import type { QuestionDetail } from '../types'
vi.mock('../lib/api', () => ({ api: vi.fn() }))
const runtime = vi.hoisted(() => ({ workspace: 'drill' }))
vi.mock('../lib/runtimePath', () => ({ get runtimeWorkspace() { return runtime.workspace } }))
let app: App | undefined
let host: HTMLDivElement
const flush = async () => { await new Promise((resolve) => setTimeout(resolve, 0)); await nextTick() }
afterEach(() => { app?.unmount(); host?.remove(); vi.resetAllMocks(); runtime.workspace = 'drill' })
async function mount() {
  uiLanguage.value = 'en'
  host = document.createElement('div'); document.body.append(host)
  const saved = vi.fn()
  app = createApp(ExamTypeEditor, { question: { uuid: 'q1', question_type: 'choice', type_group: 'small' } as QuestionDetail, onSaved: saved })
  app.mount(host); await flush()
  return saved
}
it('saves in two clicks and offers only choice, fill and large for Drill', async () => {
  vi.mocked(api).mockResolvedValueOnce({ question_type: 'choice', classification: { updated_at: 'revision1' } })
    .mockResolvedValueOnce({ question_type: 'fill', type_group: 'small' })
  const saved = await mount()
  expect(host.querySelector('.format-picker')).toBeNull()
  expect(api).not.toHaveBeenCalled()
  host.querySelector('button')!.click(); await flush()
  const options = [...host.querySelectorAll<HTMLButtonElement>('.format-option')]
  expect(options.map((b) => b.textContent)).toEqual(['Choice', 'Fill in', 'Worked solutions'])
  expect(host.textContent).not.toContain('Save')
  options[1]!.click(); await flush()
  expect(api).toHaveBeenLastCalledWith('/api/drill/questions/q1/exam-type/', {
    method: 'PATCH', body: JSON.stringify({ question_type: 'fill', expected_updated_at: 'revision1' }),
  })
  expect(saved).toHaveBeenCalledWith({ question_type: 'fill', type_group: 'small' })
  expect(host.querySelector('.format-picker')).toBeNull()
})
it('does not claim success or change the badge after a rejected save', async () => {
  vi.mocked(api).mockResolvedValueOnce({ question_type: 'choice', classification: { updated_at: 'r' } })
    .mockRejectedValueOnce(new Error('conflict'))
  const saved = await mount()
  host.querySelector('button')!.click(); await flush()
  host.querySelector<HTMLButtonElement>('.format-option')!.click(); await flush()
  expect(saved).not.toHaveBeenCalled()
  expect(host.querySelector('[role=alert]')?.textContent).toContain('Not saved')
  expect(host.querySelector('.format-trigger')?.textContent).toContain('Choice')
})

it('keeps EI judgment and short-answer options', async () => {
  runtime.workspace = 'ei'
  vi.mocked(api).mockResolvedValue({ question_type: 'choice', classification: { updated_at: 'r' } })
  await mount()
  host.querySelector('button')!.click(); await flush()
  expect([...host.querySelectorAll('.format-option')].map((b) => b.textContent)).toEqual([
    'Choice', 'Fill in', 'True / false', 'Short answer', 'Worked solutions', 'Unknown format',
  ])
})
it('prevents repeated submissions while a choice is saving', async () => {
  let complete!: (value: unknown) => void
  vi.mocked(api).mockResolvedValueOnce({ question_type: 'choice', classification: { updated_at: 'r' } })
    .mockImplementationOnce(() => new Promise((resolve) => { complete = resolve }))
  const saved = await mount()
  host.querySelector('button')!.click(); await flush()
  const option = host.querySelector<HTMLButtonElement>('.format-option')!
  option.click(); await nextTick(); option.click(); await flush()
  expect(api).toHaveBeenCalledTimes(2)
  expect(saved).not.toHaveBeenCalled()
  complete({ question_type: 'choice', type_group: 'small' }); await flush()
  expect(saved).toHaveBeenCalledTimes(1)
})

it.each(['drill', 'ei'])('shows short-answer filters only for EI (%s)', async (workspace) => {
  runtime.workspace = workspace
  uiLanguage.value = 'en'
  host = document.createElement('div'); document.body.append(host)
  app = createApp(ExamTypeControls, { modelValue: '', stats: {} }); app.mount(host); await flush()
  expect(!!host.querySelector('option[value="short_answer"]')).toBe(workspace === 'ei')
  expect(!!host.querySelector('.exam-type-stats .exam-short_answer')).toBe(workspace === 'ei')
  expect(host.textContent!.includes('true / false')).toBe(workspace === 'ei')
})
