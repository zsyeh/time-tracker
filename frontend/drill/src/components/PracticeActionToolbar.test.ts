// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { createApp, h, nextTick, type App } from 'vue'
import PracticeActionToolbar from './PracticeActionToolbar.vue'
let app: App | undefined
let host: HTMLElement
afterEach(() => { app?.unmount(); host?.remove() })
it('delegates submission to its slots and closes auxiliary actions with Escape or an outside press', async () => {
  const mastered = vi.fn(), undo = vi.fn()
  host = document.createElement('div'); document.body.append(host)
  app = createApp({ render: () => h(PracticeActionToolbar, {}, {
    primary: () => h('button', { onClick: mastered }, 'Mastered'),
    more: () => h('details', {}, [h('summary', 'More'), h('div', { class: 'practice-more-menu' }, [h('button', { onClick: undo }, 'Undo')])]),
  }) }); app.mount(host); await nextTick()
  host.querySelector('button')!.click(); expect(mastered).toHaveBeenCalledOnce()
  const details = host.querySelector('details')!, summary = host.querySelector('summary')!
  details.open = true
  summary.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
  expect(details.open).toBe(false); expect(document.activeElement).toBe(summary)
  details.open = true
  document.body.dispatchEvent(new Event('pointerdown', { bubbles: true }))
  expect(details.open).toBe(false)
  details.open = true
  host.querySelector<HTMLButtonElement>('.practice-more-menu button')!.click()
  expect(undo).toHaveBeenCalledOnce(); expect(details.open).toBe(false)
  expect(mastered).toHaveBeenCalledOnce()
})
