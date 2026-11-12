// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, defineComponent, h, nextTick, type App } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import GlobalSearch from './GlobalSearch.vue'
import { api } from '../lib/api'
vi.mock('../lib/api', () => ({ api: vi.fn() }))
vi.mock('element-plus', () => ({ ElMessage: { error: vi.fn() } }))
let app: App | undefined
let host: HTMLDivElement
const dialog = { props: ['modelValue'], template: '<div v-if="modelValue"><slot name="header" /><slot /></div>' }
const input = defineComponent({ props: { modelValue: { type: String, default: '' } }, emits: ['update:modelValue'], setup(props, { emit, attrs, expose }) { expose({ focus: vi.fn() }); return () => h('input', { ...attrs, value: props.modelValue, onInput: (event: Event) => emit('update:modelValue', (event.target as HTMLInputElement).value) }) } })
beforeEach(() => { vi.clearAllMocks(); host = document.createElement('div'); document.body.append(host); vi.mocked(api).mockResolvedValue({ results: [] }) })
afterEach(() => { app?.unmount(); app = undefined; host.remove(); vi.useRealTimers() })
async function mount() {
 const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: { template: '<div />' } }] }); await router.push('/'); await router.isReady()
 app = createApp(GlobalSearch); app.use(router)
 app.component('ElInput', input); app.component('ElDialog', dialog); app.component('ElDrawer', dialog); app.component('ElIcon', { template: '<i><slot /></i>' }); app.component('ElEmpty', { template: '<p>No results</p>' }); app.component('ElButton', { template: '<button><slot /></button>' }); app.directive('loading', {})
 app.mount(host); host.querySelector<HTMLButtonElement>('.global-search-trigger')!.click(); await nextTick(); await nextTick()
 return host.querySelector<HTMLInputElement>('input')!
}
it('defers IME queries and launches one search at composition completion', async () => {
 const field = await mount(); vi.useFakeTimers()
 field.dispatchEvent(new CompositionEvent('compositionstart', { bubbles: true })); field.value = '导'; field.dispatchEvent(new Event('input', { bubbles: true }))
 await vi.advanceTimersByTimeAsync(300); expect(api).not.toHaveBeenCalled()
 field.value = '导数'; field.dispatchEvent(new Event('input', { bubbles: true })); field.dispatchEvent(new CompositionEvent('compositionend', { bubbles: true }))
 await vi.advanceTimersByTimeAsync(250); await nextTick()
 expect(api).toHaveBeenCalledTimes(1)
 expect(String(vi.mocked(api).mock.calls[0]?.[0])).toContain(encodeURIComponent('导数'))
})
it('aborts and invalidates the old result before the next debounce expires', async () => {
 const field = await mount(); vi.useFakeTimers()
 let finish!: (value: unknown) => void
 vi.mocked(api).mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
 field.value = 'old'; field.dispatchEvent(new Event('input', { bubbles: true })); await vi.advanceTimersByTimeAsync(250)
 const signal = vi.mocked(api).mock.calls[0]?.[1]?.signal
 field.value = 'new'; field.dispatchEvent(new Event('input', { bubbles: true })); expect(signal?.aborted).toBe(true)
 finish({ results: [{ kind: 'issue', record_id: 1, title: 'Stale private result', snippet: 'old', subject_label: '', occurred_at: '2026-01-01' }] }); await nextTick(); await nextTick()
 expect(host.textContent).not.toContain('Stale private result')
 await vi.advanceTimersByTimeAsync(250); expect(api).toHaveBeenCalledTimes(2)
})
