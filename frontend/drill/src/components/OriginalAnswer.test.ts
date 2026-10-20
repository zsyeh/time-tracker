// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import OriginalAnswer from './OriginalAnswer.vue'
import { api } from '../lib/api'

vi.mock('../lib/api', () => ({ api: vi.fn() }))
let app: App | undefined
let host: HTMLDivElement
afterEach(() => { app?.unmount(); host?.remove(); vi.resetAllMocks() })

async function mount() {
  host = document.createElement('div'); document.body.append(host)
  app = createApp(OriginalAnswer, { uuid: 'original-paper' }); app.mount(host)
  await nextTick()
  return host.querySelector('details')!
}
async function toggle(details: HTMLDetailsElement, open: boolean) {
  details.open = open
  await new Promise((resolve) => setTimeout(resolve, 0)); await nextTick()
}

describe('complete original answers', () => {
  it('loads only when expanded and keeps original page order without repeat fetches', async () => {
    vi.mocked(api).mockResolvedValue({ answer_assets: [
      { id: 1, url: '/page1', width: 600, height: 800 },
      { id: 2, url: '/page2', width: 600, height: 800 },
    ], answer_markdown: '' })
    const details = await mount()
    expect(api).not.toHaveBeenCalled()
    expect(host.querySelectorAll('img')).toHaveLength(0)
    await toggle(details, true)
    expect(api).toHaveBeenCalledWith('/api/drill/questions/original-paper/')
    expect([...host.querySelectorAll('img')].map((i) => i.getAttribute('src'))).toEqual(['/page1', '/page2'])
    await toggle(details, false); await toggle(details, true)
    expect(api).toHaveBeenCalledTimes(1)
  })
  it('shows an error and allows a new expansion to retry', async () => {
    vi.mocked(api).mockRejectedValueOnce(new Error('Network unavailable'))
      .mockResolvedValueOnce({ answer_assets: [], answer_markdown: '' })
    const details = await mount(); await toggle(details, true)
    expect(host.querySelector('[role="alert"]')?.textContent).toBe('Network unavailable')
    await toggle(details, false); await toggle(details, true)
    expect(api).toHaveBeenCalledTimes(2)
    expect(host.querySelector('[role="alert"]')).toBeNull()
  })
})
