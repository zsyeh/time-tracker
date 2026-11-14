// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, h, nextTick, ref, type App } from 'vue'
import StudyTimerGuard from './StudyTimerGuard.vue'
import { activeStudyTimer, startStudyTimer } from '../lib/studyTimer'
import type { StudyTimerMode } from '../../../shared/preferences/schema'
vi.mock('../lib/studyTimer', () => ({ activeStudyTimer: vi.fn(), startStudyTimer: vi.fn(), studySubject: (s: string) => s === 'drill' ? 'math' : 'major' }))
vi.mock('../lib/examTypes', () => ({ typeText: (_zh: string, en: string) => en }))
const mounted: App[] = []
const settle = async () => { await nextTick(); await nextTick(); await nextTick() }
function setup(initial: StudyTimerMode = 'remind', workspace: 'drill' | 'ei' = 'drill') {
  const mode = ref(initial), context = ref('question-1'), instance = ref<InstanceType<typeof StudyTimerGuard> | null>(null)
  const root = document.createElement('div'); document.body.append(root)
  const app = createApp({ render: () => h(StudyTimerGuard, { ref: instance, workspace, mode: mode.value, context: context.value, 'onUpdate:mode': (v: StudyTimerMode) => { mode.value = v } }) })
  app.mount(root); mounted.push(app)
  return { mode, context, ensure: () => instance.value!.ensure() }
}
const click = (label: string) => Array.from(document.querySelectorAll('button')).find(b => b.textContent === label)!.click()
beforeEach(() => {
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value() { this.open = true } })
  Object.defineProperty(HTMLDialogElement.prototype, 'close', { configurable: true, value() { this.open = false } })
  vi.mocked(activeStudyTimer).mockResolvedValue(null)
  vi.mocked(startStudyTimer).mockResolvedValue({ id: 1, subject: 'math' })
})
afterEach(() => { mounted.splice(0).forEach(app => app.unmount()); document.body.innerHTML = ''; vi.resetAllMocks() })
it('does not request anything in off mode', async () => {
  expect(await setup('off').ensure()).toBe(true)
  expect(activeStudyTimer).not.toHaveBeenCalled(); expect(startStudyTimer).not.toHaveBeenCalled()
})
it('saves directly when the corresponding subject is running', async () => {
  vi.mocked(activeStudyTimer).mockResolvedValue({ id: 1, subject: 'math' })
  expect(await setup().ensure()).toBe(true)
  expect(document.querySelector('dialog')?.open).toBe(false)
  expect(startStudyTimer).not.toHaveBeenCalled()
})
it('allows cancel without starting a timer or changing preferences', async () => {
  const guard = setup(), result = guard.ensure(); await settle()
  expect(document.querySelector('dialog')?.open).toBe(true)
  click('Cancel'); expect(await result).toBe(false); expect(guard.mode.value).toBe('remind')
  expect(startStudyTimer).not.toHaveBeenCalled()
})
it('starts the timer explicitly, then releases submission', async () => {
  const guard = setup(), result = guard.ensure(); await settle()
  click('Start timer & save'); await settle()
  expect(await result).toBe(true); expect(startStudyTimer).toHaveBeenCalledExactlyOnceWith('drill')
})
it('persists do-not-remind only after continuing', async () => {
  const guard = setup(), result = guard.ensure(); await settle()
  const checkbox = document.querySelector('input')!; checkbox.checked = true; checkbox.dispatchEvent(new Event('change'))
  click('Save anyway'); expect(await result).toBe(true); expect(guard.mode.value).toBe('off')
})
it('auto-starts EI using its own subject without showing a popup', async () => {
  expect(await setup('auto_start', 'ei').ensure()).toBe(true)
  expect(startStudyTimer).toHaveBeenCalledExactlyOnceWith('ei')
  expect(document.querySelector('dialog')?.open).toBe(false)
})
it('never starts or stops a different subject, including in automatic mode', async () => {
  vi.mocked(activeStudyTimer).mockResolvedValue({ id: 2, subject: 'english' })
  const result = setup('auto_start').ensure(); await settle()
  expect(document.body.textContent).toContain('different subject')
  expect(document.body.textContent).not.toContain('Start timer & save')
  click('Save anyway'); expect(await result).toBe(true); expect(startStudyTimer).not.toHaveBeenCalled()
})
it('keeps answer saving available after a check failure', async () => {
  vi.mocked(activeStudyTimer).mockRejectedValue(new Error('offline'))
  const result = setup().ensure(); await settle()
  expect(document.body.textContent).toContain('could not be checked')
  click('Save anyway'); expect(await result).toBe(true)
})
it('keeps answer saving available after an automatic start failure', async () => {
  vi.mocked(startStudyTimer).mockRejectedValue(new Error('conflict'))
  const result = setup('auto_start').ensure(); await settle()
  expect(document.body.textContent).toContain('could not be started automatically')
  click('Save anyway'); expect(await result).toBe(true); expect(startStudyTimer).toHaveBeenCalledTimes(1)
})
it('discards a late check after the question context changes', async () => {
  let resolve!: (value: null) => void
  vi.mocked(activeStudyTimer).mockReturnValue(new Promise(done => { resolve = done }))
  const guard = setup('auto_start'), result = guard.ensure()
  guard.context.value = 'question-2'; await settle(); resolve(null)
  expect(await result).toBe(false); expect(startStudyTimer).not.toHaveBeenCalled()
})
