// @vitest-environment jsdom
import { bindTestPreferences, clearTestPreferences } from '../../../shared/preferences/testSupport'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import LearningSharePanel from './LearningSharePanel.vue'
import { api, post } from '../lib/api'
import { uiLanguage } from '../lib/uiPreferences'

vi.mock('../lib/api', () => ({ api: vi.fn(), post: vi.fn(), remove: vi.fn() }))
let app: App | undefined
let host: HTMLDivElement
beforeEach(async () => { localStorage.clear(); await bindTestPreferences() })
afterEach(() => {
  app?.unmount()
  host?.remove()
  uiLanguage.value = 'en'
  clearTestPreferences()
  vi.resetAllMocks()
})

async function flush() { await new Promise((resolve) => setTimeout(resolve, 0)); await nextTick() }

describe('AI share panel language and disclosure', () => {
  it('keeps the same share request while the interface and copied prompt switch languages', async () => {
    vi.mocked(api).mockResolvedValue({ shares: [] })
    vi.mocked(post).mockResolvedValue({ id: 7, kind: 'heatmap', scope: {}, include_notes: true,
      expires_at: '2026-11-16T00:00:00Z', url: 'https://drill.ehzsy.site/share/learning/token/index.md' })
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } })
    uiLanguage.value = 'zh-CN'
    host = document.createElement('div')
    document.body.append(host)
    app = createApp(LearningSharePanel, { currentScope: { state: 'review' } })
    app.mount(host)
    await flush()

    const panel = host.querySelector('details')!
    expect(panel.open).toBe(false)
    expect(panel.querySelector('summary')?.textContent).toContain('AI 分享')
    panel.open = true
    await flush()
    const createButton = [...host.querySelectorAll('button')].find((button) => button.textContent?.includes('生成 7 天链接'))!
    createButton.click()
    await flush()
    expect(post).toHaveBeenCalledWith('/api/drill/learning-shares/', {
      kind: 'heatmap', scope: { state: 'review' }, include_notes: true,
    })

    uiLanguage.value = 'en'
    await nextTick()
    expect(panel.querySelector('summary')?.textContent).toContain('AI share')
    const promptButton = [...host.querySelectorAll('button')].find((button) => button.textContent?.includes('Copy prompt'))!
    promptButton.click()
    await flush()
    expect(writeText).toHaveBeenCalledWith(expect.stringContaining('Do not invent'))
    expect(post).toHaveBeenCalledTimes(1)
  })
})
