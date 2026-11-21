// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { installPracticeKeyboardViewport } from './practiceKeyboardViewport'
let dispose = () => {}
afterEach(() => { dispose(); vi.unstubAllGlobals(); vi.restoreAllMocks(); document.body.innerHTML = '' })
function setup(apple = true) {
  vi.spyOn(navigator, 'platform', 'get').mockReturnValue(apple ? 'MacIntel' : 'Linux')
  vi.stubGlobal('navigator', { userAgent: 'test', platform: apple ? 'MacIntel' : 'Linux', maxTouchPoints: apple ? 5 : 0 })
  const viewport = Object.assign(new EventTarget(), { height: 820, offsetTop: 0, scale: 1 })
  const split = Object.assign(new EventTarget(), { matches: true })
  vi.stubGlobal('visualViewport', viewport)
  vi.stubGlobal('innerHeight', 820)
  vi.stubGlobal('matchMedia', () => split)
  vi.stubGlobal('requestAnimationFrame', (fn: FrameRequestCallback) => window.setTimeout(() => fn(0), 0))
  vi.stubGlobal('cancelAnimationFrame', clearTimeout)
  document.body.innerHTML = '<div class="drill-shell question-route"><div class="question-control-pane"><textarea></textarea></div></div>'
  dispose = installPracticeKeyboardViewport()
  return { viewport, split, shell: document.querySelector<HTMLElement>('.drill-shell')!, editor: document.querySelector('textarea')! }
}
it('tracks keyboard height and Safari pan on focus and Enter without cancelling input', async () => {
  const { viewport, shell, editor } = setup()
  editor.focus();viewport.height = 420;viewport.offsetTop = 96;viewport.dispatchEvent(new Event('resize'))
  await vi.waitFor(() => expect(shell.style.getPropertyValue('--practice-visible-height')).toBe('420px'))
  expect(shell.style.getPropertyValue('--practice-visible-top')).toBe('96px')
  const enter = new KeyboardEvent('keydown', { key: 'Enter', cancelable: true });editor.dispatchEvent(enter)
  expect(enter.defaultPrevented).toBe(false)
  viewport.offsetTop = 132;viewport.dispatchEvent(new Event('scroll'))
  await vi.waitFor(() => expect(shell.style.getPropertyValue('--practice-visible-top')).toBe('132px'))
  editor.blur();viewport.height = 820;viewport.offsetTop = 0;viewport.dispatchEvent(new Event('resize'))
  await vi.waitFor(() => expect(shell.classList.contains('practice-keyboard-viewport')).toBe(false))
})
it('cleans up on route leave and does not retain viewport handlers', async () => {
  const { viewport, shell, editor } = setup();editor.focus();viewport.height = 420;viewport.dispatchEvent(new Event('resize'))
  await vi.waitFor(() => expect(shell.classList.contains('practice-keyboard-viewport')).toBe(true))
  dispose();expect(shell.style.getPropertyValue('--practice-visible-height')).toBe('')
  viewport.dispatchEvent(new Event('resize'));await new Promise(r => setTimeout(r, 10))
  expect(shell.classList.contains('practice-keyboard-viewport')).toBe(false)
})
it('leaves desktop, portrait and pinch zoom alone', async () => {
  const { viewport, split, shell, editor } = setup();editor.focus();viewport.height = 420;split.matches = false;viewport.dispatchEvent(new Event('resize'))
  await new Promise(r => setTimeout(r, 10));expect(shell.classList.contains('practice-keyboard-viewport')).toBe(false)
  split.matches = true;viewport.scale = 1.5;viewport.dispatchEvent(new Event('resize'))
  await new Promise(r => setTimeout(r, 10));expect(shell.classList.contains('practice-keyboard-viewport')).toBe(false)
  dispose();setup(false);expect(shell.classList.contains('practice-keyboard-viewport')).toBe(false)
})
