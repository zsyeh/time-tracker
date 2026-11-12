// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import ElementPlus from 'element-plus'
import SettingsView from './SettingsView.vue'

const requests = vi.hoisted(() => ({ api: vi.fn(), patch: vi.fn(), post: vi.fn(), put: vi.fn(), remove: vi.fn() }))
vi.mock('../lib/api', () => requests)
vi.mock('../lib/uiPreferences', async () => {
  const { ref } = await import('vue')
  return { useUiPreferences: () => ({ language: ref('en'), setLanguage: vi.fn(), t: (value: string) => value }) }
})
vi.mock('../../shared/appearance/preferences', async () => {
  const { ref } = await import('vue')
  return { useAppearance: () => ({ appearance: ref('system'), accent: ref('blue'), setAppearance: vi.fn(), setAccent: vi.fn() }) }
})
vi.mock('../../shared/ui/AppearanceSelector.vue', () => ({ default: { template: '<button>System</button>' } }))
vi.mock('../../shared/ui/AccentColorPicker.vue', () => ({ default: { template: '<button>Blue</button>' } }))

let app: App | undefined
let host: HTMLDivElement
let router: Router
let superuser = true
const runtime = { homepage_content: 'Saved homepage', study_room_code: '', tracking_start_date: '2026-05-23', exam_date: '2026-12-19', countdown_label: 'Goal' }
const token = { id: 1, name: 'Synthetic capability', subject: 'math', usage_count: 1, max_uses: null,
  available_from: '06:00:00', available_until: '22:00:00', within_schedule: true,
  credential_valid: true, is_paused: false, usable: true, is_active: true, has_disturbance_uri: true }

async function settle() {
  for (let n = 0; n < 4; n++) { await Promise.resolve(); await nextTick() }
  await new Promise(resolve => setTimeout(resolve, 5))
}
async function mount(path = '/settings') {
  router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/settings', component: SettingsView }] })
  await router.push(path); await router.isReady()
  app = createApp(SettingsView); app.use(router); app.use(ElementPlus); app.mount(host)
  await settle()
}
function panels() {
  return [...host.querySelectorAll<HTMLElement>('.settings-content > section,.settings-content > article')]
    .filter(element => element.style.display !== 'none').map(element => element.id)
}
async function choose(section: string) {
  host.querySelector<HTMLAnchorElement>(`.settings-index a[href="?section=${section}"]`)!.click()
  await settle()
}
beforeEach(() => {
  superuser = true
  vi.clearAllMocks()
  host = document.createElement('div'); document.body.append(host)
  vi.stubGlobal('ResizeObserver', class { observe = vi.fn(); unobserve = vi.fn(); disconnect = vi.fn() })
  Element.prototype.scrollIntoView = vi.fn()
  requests.api.mockImplementation(async (url: string) => {
    if (url === '/api/auth/session/') return { user: { username: 'Synthetic owner', is_staff: superuser, is_superuser: superuser } }
    if (url === '/api/settings/runtime/') return { values: runtime, defaults: runtime, local_env_exists: true }
    if (url === '/api/settings/data-encryption/') return { enabled: false, algorithm: 'AES-256-GCM' }
    if (url === '/api/launch-tokens/') return [token]
    return []
  })
})
afterEach(() => {
  app?.unmount(); app = undefined; host.remove()
  document.body.replaceChildren()
  vi.unstubAllGlobals()
})

it('uses one independent panel per section without scrolling or changing business state', async () => {
  await mount()
  expect(panels()).toEqual(['general'])
  for (const [section, panel] of Object.entries({ appearance: 'appearance', instance: 'instance', security: 'privacy', access: 'access', data: 'data', organization: 'organization', invitations: 'invitations', shortcuts: 'shortcuts', general: 'general' })) {
    await choose(section)
    expect(router.currentRoute.value.query.section).toBe(section)
    expect(panels()).toEqual([panel])
    expect(host.querySelector(`.settings-index a[href="?section=${section}"]`)?.getAttribute('aria-current')).toBe('location')
  }
  expect(Element.prototype.scrollIntoView).not.toHaveBeenCalled()
  for (const key of ['post', 'put', 'patch', 'remove'] as const) expect(requests[key]).not.toHaveBeenCalled()
  expect(host.querySelectorAll('.capability-actions button')).toHaveLength(5)
  expect(host.querySelector('a[href="/api/export/markdown/"]')).not.toBeNull()
  expect(host.querySelector('a[href="/admin/tracker/invitecode/auth-recovery/"]')).not.toBeNull()
})

it('keeps unsaved form values and the same mounted controls across section changes', async () => {
  await mount('/settings?section=instance')
  const textarea = host.querySelector<HTMLTextAreaElement>('.runtime-settings-form textarea')!
  textarea.value = 'Unsaved local edit'; textarea.dispatchEvent(new Event('input', { bubbles: true }))
  await settle(); await choose('shortcuts'); await choose('instance')
  expect(host.querySelector('.runtime-settings-form textarea')).toBe(textarea)
  expect(textarea.value).toBe('Unsaved local edit')
  expect(requests.put).not.toHaveBeenCalled()
})

it('maps legacy hashes to the correct panel and lets an explicit section win', async () => {
  await mount('/settings#privacy'); expect(panels()).toEqual(['privacy'])
  await router.replace('/settings#access'); await settle(); expect(panels()).toEqual(['access'])
  await router.replace('/settings#shortcuts'); await settle(); expect(panels()).toEqual(['shortcuts'])
  await router.replace('/settings?section=appearance#privacy'); await settle(); expect(panels()).toEqual(['appearance'])
  await router.replace('/settings?section=missing#unknown'); await settle(); expect(panels()).toEqual(['general'])
  expect(Element.prototype.scrollIntoView).not.toHaveBeenCalled()
})

it('provides every permitted section in the mobile selector', async () => {
  await mount()
  const select = host.querySelector<HTMLSelectElement>('.settings-mobile-section select')!
  expect([...select.options].map(option => option.value)).toEqual(expect.arrayContaining(['instance', 'access', 'security', 'shortcuts']))
  select.value = 'access'; select.dispatchEvent(new Event('change', { bubbles: true })); await settle()
  expect(panels()).toEqual(['access'])
})

it('keeps instance controls unavailable to ordinary accounts even through a deep link', async () => {
  superuser = false
  await mount('/settings?section=instance')
  expect(panels()).toEqual(['general'])
  expect(host.querySelector('#instance')).toBeNull()
  expect(host.querySelector('.settings-index a[href="?section=instance"]')).toBeNull()
  expect(host.querySelector('.settings-mobile-section option[value=instance]')).toBeNull()
  expect(host.querySelector('.admin-console-card')).toBeNull()
  await choose('access'); expect(panels()).toEqual(['access'])
})
