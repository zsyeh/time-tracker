// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it } from 'vitest'
import { createApp, h, nextTick, reactive, type App } from 'vue'
import PracticePagination from './PracticePagination.vue'
let app: App | undefined, host: HTMLDivElement
beforeEach(() => { host = document.createElement('div'); document.body.append(host) })
afterEach(() => { app?.unmount(); host.remove() })
function mount(options = { page: 2, totalPages: 5, count: 97, loading: false }) {
  const state = reactive(options), changes: Array<[number,string]> = []
  app = createApp({ setup: () => () => h(PracticePagination, { ...state, position: 'bottom', onChange: (page, position) => changes.push([page,position]) }) })
  app.mount(host)
  return { state, changes }
}
function submit(value: string) { const input = host.querySelector<HTMLInputElement>('input')!; input.value = value; input.dispatchEvent(new Event('input')); host.querySelector('form')!.dispatchEvent(new Event('submit', { cancelable:true })); }
it('shows the current and total pages and keeps top/bottom origin with page requests', () => {
  const { changes } = mount()
  expect(host.querySelector('.page-summary')!.textContent).toContain('2 / 5')
  expect(host.querySelector('.page-summary')!.textContent).toContain('97')
  host.querySelector<HTMLButtonElement>('.page-next')!.click()
  host.querySelector<HTMLButtonElement>('.page-previous')!.click()
  expect(changes).toEqual([[3,'bottom'],[1,'bottom']])
})
it('accepts any valid integer page and rejects out-of-range, fractional and exponential input', async () => {
  const { changes } = mount()
  for (const invalid of ['0','6','1.5','1e2','']) { submit(invalid); await nextTick(); expect(host.querySelector('[role=alert]')).not.toBeNull() }
  expect(changes).toEqual([])
  submit('2'); await nextTick()
  expect(changes).toEqual([]); expect(host.querySelector('[role=alert]')).toBeNull()
  submit('4'); await nextTick()
  expect(changes).toEqual([[4,'bottom']]); expect(host.querySelector('[role=alert]')).toBeNull()
})
it('disables navigation and page entry while loading or when the result is empty', async () => {
  const { state, changes } = mount({ page:1,totalPages:0,count:0,loading:false })
  expect(host.querySelector('.page-summary')!.textContent).toContain('0 / 0')
  expect([...host.querySelectorAll<HTMLButtonElement>('button')].every(button => button.disabled)).toBe(true)
  state.totalPages = 5; state.count = 97; state.loading = true; await nextTick()
  submit('3'); await nextTick()
  expect(changes).toEqual([]); expect(host.querySelector<HTMLInputElement>('input')!.disabled).toBe(true)
})
it('updates the jump draft when URL navigation changes the current page', async () => {
  const { state } = mount(); submit('99'); await nextTick()
  state.page = 4; await nextTick()
  expect(host.querySelector<HTMLInputElement>('input')!.value).toBe('4')
  expect(host.querySelector('[role=alert]')).toBeNull()
})

it('exposes explicit first and last pages with correct boundary states',async()=>{
 const {state,changes}=mount()
 host.querySelector<HTMLButtonElement>('.page-first')!.click();host.querySelector<HTMLButtonElement>('.page-last')!.click()
 expect(changes).toEqual([[1,'bottom'],[5,'bottom']])
 state.page=1;await nextTick()
 expect(host.querySelector<HTMLButtonElement>('.page-first')!.disabled).toBe(true)
 expect(host.querySelector<HTMLButtonElement>('.page-previous')!.disabled).toBe(true)
 expect(host.querySelector<HTMLButtonElement>('.page-last')!.disabled).toBe(false)
 state.page=5;await nextTick()
 expect(host.querySelector<HTMLButtonElement>('.page-last')!.disabled).toBe(true)
 expect(host.querySelector<HTMLButtonElement>('.page-next')!.disabled).toBe(true)
 expect(host.querySelector<HTMLButtonElement>('.page-first')!.disabled).toBe(false)
})
it('keeps first/last controls in native keyboard focus order and supports form submission for a direct jump',async()=>{
 const {changes}=mount()
 for(const selector of ['.page-first','.page-last']){
  const control=host.querySelector<HTMLButtonElement>(selector)!
  expect(control.tagName).toBe('BUTTON');expect(control.type).toBe('button');expect(control.tabIndex).toBe(0)
  expect(control.getAttribute('aria-label')).toBeTruthy();control.focus();expect(document.activeElement).toBe(control)
 }
 const input=host.querySelector<HTMLInputElement>('input')!
 input.focus();input.value='5';input.dispatchEvent(new Event('input'))
 host.querySelector<HTMLFormElement>('form')!.requestSubmit();await nextTick()
 expect(changes).toEqual([[5,'bottom']])
})

it('keeps navigation-restored focus read-only until an explicit editing gesture', async () => {
 mount({ page: 1, totalPages: 20, count: 480, loading: false })
 const input = host.querySelector<HTMLInputElement>('input')!
 expect(input.readOnly).toBe(true); expect(input.inputMode).toBe('none')
 input.focus(); expect(input.readOnly).toBe(true)
 input.dispatchEvent(new Event('pointerdown', { bubbles: true }))
 expect(input.readOnly).toBe(false); expect(input.inputMode).toBe('numeric')
 input.blur(); await nextTick(); expect(input.readOnly).toBe(true)
 input.focus(); input.dispatchEvent(new KeyboardEvent('keydown', { key: '2', bubbles: true }))
 expect(input.readOnly).toBe(false)
})
