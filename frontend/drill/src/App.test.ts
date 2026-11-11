// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, defineComponent, h, nextTick, reactive, type App } from 'vue'
import AppShell from './App.vue'
import { api } from './lib/api'
import { uiLanguage } from './lib/uiPreferences'

const route = reactive({ name: 'practice', fullPath: '/practice', query: {} as Record<string, string> })
const runtime = vi.hoisted(() => ({ workspace: 'drill' }))
vi.mock('vue-router', () => ({ useRoute: () => route, useRouter: () => ({ replace: vi.fn() }) }))
vi.mock('./lib/api', () => ({ api: vi.fn(), post: vi.fn() }))
vi.mock('./lib/workspace', () => ({ configureWorkspaceScope: vi.fn() }))
vi.mock('../../shared/learningRecovery', () => ({ startLearningRecovery: vi.fn().mockResolvedValue(() => {}) }))
vi.mock('./lib/runtimePath', () => ({ get runtimeWorkspace() { return runtime.workspace } }))

const RouterLink = defineComponent({
  props: ['to'],
  setup(props, { attrs, slots }) {
    return () => h('a', { ...attrs, href: props.to }, slots.default?.())
  },
})
let app: App | undefined
let host: HTMLDivElement

async function settle() { await Promise.resolve(); await nextTick(); await nextTick() }
async function mount() {
  host = document.createElement('div')
  document.body.append(host)
  app = createApp(AppShell)
  app.component('RouterLink', RouterLink)
  app.component('RouterView', { template: '<div />' })
  app.mount(host)
  await settle()
}

beforeEach(() => {
  localStorage.clear()
  runtime.workspace = 'drill'
  uiLanguage.value = 'en'
  route.name = 'practice'
  route.fullPath = '/practice'
  route.query = {}
  vi.mocked(api).mockImplementation(async (path) => path.includes('/auth/session/')
    ? { user: { username: 'student', id: 1 } }
    : { attempted_questions: 12, question_count: 48, total_attempts: 15 })
})

it('keeps EI entry points and all EI tools available without a Drill heatmap home', async () => {
  runtime.workspace = 'ei'
  route.name = 'cockpit'
  route.fullPath = '/cockpit'
  await mount()
  expect(host.querySelector('.primary-navigation')?.textContent).toContain('892 overview')
  expect(host.querySelector('.primary-navigation')?.textContent).not.toContain('Selected Heatmap')
  host.querySelector<HTMLButtonElement>('.more-tools-trigger')!.click()
  await settle()
  const panel = document.querySelector<HTMLElement>('#more-tools-panel')!
  expect(panel.querySelectorAll('a')).toHaveLength(16)
  expect(panel.textContent).toContain('Selected circuits')
  expect(panel.textContent).toContain('Selected PDF page log')
})
afterEach(() => { app?.unmount(); host?.remove(); app = undefined; vi.clearAllMocks() })

it('opens all secondary links in a scrollable popover and closes on Escape', async () => {
  await mount()
  const trigger = host.querySelector<HTMLButtonElement>('.more-tools-trigger')!
  expect(trigger.getAttribute('aria-expanded')).toBe('false')
  trigger.click()
  await settle()
  const panel = document.querySelector<HTMLElement>('#more-tools-panel')!
  expect(trigger.getAttribute('aria-expanded')).toBe('true')
  expect(panel.querySelectorAll('a')).toHaveLength(9)
  expect(panel.textContent).toContain('Favorites')
  expect(panel.textContent).toContain('Corrections')
  expect(panel.style.maxHeight).not.toBe('')
  document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
  await settle()
  expect(document.querySelector('#more-tools-panel')).toBeNull()
  expect(document.activeElement).toBe(trigger)
})

it('keeps the current secondary destination marked and closes on route change or outside click', async () => {
  await mount()
  route.name = 'heatmap'
  route.fullPath = '/heatmap'
  await settle()
  const trigger = host.querySelector<HTMLButtonElement>('.more-tools-trigger')!
  expect(trigger.classList.contains('active')).toBe(true)
  trigger.click()
  await settle()
  expect(document.querySelector<HTMLAnchorElement>('#more-tools-panel a[href="/heatmap"]')?.classList.contains('active')).toBe(true)
  document.body.dispatchEvent(new Event('pointerdown', { bubbles: true }))
  await settle()
  expect(document.querySelector('#more-tools-panel')).toBeNull()
  trigger.click()
  await settle()
  route.name = 'insight'
  route.fullPath = '/insight'
  await settle()
  expect(document.querySelector('#more-tools-panel')).toBeNull()
  expect(trigger.classList.contains('active')).toBe(false)
})
