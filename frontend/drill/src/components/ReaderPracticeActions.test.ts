// @vitest-environment jsdom
import { bindTestPreferences, clearTestPreferences } from '../../../shared/preferences/testSupport'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, h, nextTick, reactive, type App } from 'vue'
import ReaderPracticeActions from './ReaderPracticeActions.vue'
import type { ReaderPracticeControls } from '../lib/readerPractice'
import { uiLanguage } from '../lib/uiPreferences'
let app: App | undefined
let host: HTMLElement
beforeEach(async () => { localStorage.clear(); await bindTestPreferences() })
afterEach(() => { app?.unmount(); host?.remove(); clearTestPreferences() })
async function mount() {
  uiLanguage.value = 'en'
  const controls = reactive<ReaderPracticeControls>({ mode: 'sequential', canPrevious: true, canNext: true, canAnswer: true, busy: false, masteredAutoNext: true, reviewAutoNext: false, state: 'unattempted', error: '', feedback: '' })
  const action = vi.fn()
  host = document.createElement('div'); document.body.append(host)
  app = createApp({ render: () => h(ReaderPracticeActions, { controls, onAction: action }) }); app.mount(host); await nextTick()
  return { controls, action }
}
it('renders exactly five icon-only controls and emits actions without its own submission logic', async () => {
  const { action, controls } = await mount()
  const buttons = [...host.querySelectorAll<HTMLButtonElement>('button')]
  expect(buttons.map(b => b.dataset.action)).toEqual(['previous', 'next', 'mastered', 'review', 'answer'])
  expect(buttons.every(b => !b.textContent?.trim() && b.querySelector('svg'))).toBe(true)
  buttons[2]!.click(); expect(action).toHaveBeenLastCalledWith('mastered')
  controls.busy = true; await nextTick()
  expect(buttons.every(b => b.disabled)).toBe(true)
  buttons[1]!.click(); expect(action).toHaveBeenCalledTimes(1)
})
it('updates route colors, labels and automatic-jump markers from the live page preferences', async () => {
  const { controls } = await mount()
  const next = host.querySelector('[data-action=next]')!
  const mastered = host.querySelector('[data-action=mastered]')!
  const review = host.querySelector('[data-action=review]')!
  expect(mastered.getAttribute('title')).toContain('sequential')
  expect(review.getAttribute('title')).toBe('Needs review')
  controls.mode = 'overdue'; await nextTick()
  expect(next.getAttribute('title')).toContain('red overdue')
  expect(next.querySelectorAll('path')[1]!.getAttribute('stroke')).toContain('--danger')
  expect(mastered.querySelectorAll('path')[1]!.getAttribute('stroke')).toContain('--danger')
  controls.mode = 'review'; controls.reviewAutoNext = true; await nextTick()
  expect(next.querySelectorAll('path')[1]!.getAttribute('stroke')).toContain('--warning')
  expect(review.querySelectorAll('path')[1]!.getAttribute('stroke')).toContain('color-mix')
  controls.masteredAutoNext = false; await nextTick()
  expect(mastered.querySelectorAll('path')).toHaveLength(1)
  expect(mastered.getAttribute('title')).toBe('Mastered')
})

it('announces the answer toggle state and keeps both directions available', async () => {
  const { controls, action } = await mount()
  const button = host.querySelector<HTMLButtonElement>('[data-action=answer]')!
  expect(button.getAttribute('aria-pressed')).toBe('false')
  expect(button.getAttribute('aria-label')).toBe('Show answer')
  button.click()
  controls.answerActive = true; await nextTick()
  expect(button.getAttribute('aria-pressed')).toBe('true')
  expect(button.getAttribute('aria-label')).toBe('Back to question')
  button.click()
  expect(action.mock.calls).toEqual([['answer'], ['answer']])
  uiLanguage.value = 'zh-CN'; await nextTick()
  expect(button.getAttribute('aria-label')).toBe('返回题目')
})

it('shows grey unattempted arrows and disables exhausted destinations without emitting navigation', async () => {
  const { controls, action } = await mount()
  controls.mode = 'unattempted'; controls.reviewAutoNext = true; await nextTick()
  for (const name of ['previous', 'next', 'mastered', 'review']) {
    const button = host.querySelector<HTMLButtonElement>(`[data-action=${name}]`)!
    expect(button.getAttribute('title')).toContain('unattempted')
    expect(button.querySelectorAll('path')[1]!.getAttribute('stroke')).toContain('--text-tertiary')
  }
  controls.canPrevious = false; controls.canNext = false; await nextTick()
  const previous = host.querySelector<HTMLButtonElement>('[data-action=previous]')!
  const next = host.querySelector<HTMLButtonElement>('[data-action=next]')!
  expect(previous.disabled).toBe(true); expect(next.disabled).toBe(true)
  previous.click(); next.click(); expect(action).not.toHaveBeenCalled()
  uiLanguage.value = 'zh-CN'; await nextTick()
  expect(next.getAttribute('aria-label')).toContain('未做题')
})
