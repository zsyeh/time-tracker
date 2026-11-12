// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import SettingsView from './SettingsView.vue'
import { bindTestPreferences, clearTestPreferences } from '../../../shared/preferences/testSupport'
import { accountPreferences } from '../../../shared/preferences/store'
import { usePracticePreferences } from '../lib/practicePreferences'
vi.mock('../lib/api', () => ({ api: vi.fn(async () => ({ user: { username: 'Learner' } })) }))
let app: App | undefined
let host: HTMLDivElement
beforeEach(async () => { localStorage.clear(); await bindTestPreferences('en', 'settings-test'); host = document.createElement('div'); document.body.append(host) })
afterEach(() => { app?.unmount(); app = undefined; host.remove(); clearTestPreferences() })
it('shows the real account, management destinations and independent appearance settings', async () => {
 app = createApp(SettingsView); app.mount(host); await nextTick(); await nextTick()
 expect(host.textContent).toContain('Learner')
 expect(host.querySelector('#settings-appearance')).not.toBeNull()
 expect(host.querySelectorAll('a[href^="https://47.95.10.128/settings?section="]')).toHaveLength(5)
 expect(host.querySelector('a[href="/accounts/2fa/"]')).not.toBeNull()
 expect(host.querySelector('#settings-source')).not.toBeNull()
})
it('edits the existing practice refs and queues their account-owned persistence', async () => {
 const preferences = usePracticePreferences()
 preferences.reviewAutoNext.value = false
 app = createApp(SettingsView); app.mount(host); await nextTick()
 const switches = host.querySelectorAll<HTMLInputElement>('[aria-labelledby=settings-practice] input[role=switch]')
 expect(switches).toHaveLength(2)
 switches[1]!.checked = true; switches[1]!.dispatchEvent(new Event('change', { bubbles: true })); await nextTick()
 expect(preferences.reviewAutoNext.value).toBe(true)
 expect(accountPreferences.values['practice.review_auto_next']).toBe(true)
 const queued = JSON.parse(localStorage.getItem('learning.preferences.v1.settings-test')!)
 expect(queued.pending['practice.review_auto_next'].value).toBe(true)
 expect(preferences.masteredAutoNext.value).toBe(switches[0]!.checked)
})
