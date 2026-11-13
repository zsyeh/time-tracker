// @vitest-environment jsdom
import {afterEach, beforeEach, expect, it, vi} from 'vitest'
import {createApp, h, nextTick, ref, type App} from 'vue'
import UiPopover from './UiPopover.vue'
import UiMenu, {type MenuItem} from './UiMenu.vue'

const mounted: App[] = []
const settle = async () => { await nextTick(); await nextTick() }
function setupMenu(items: MenuItem[]) {
  const anchor = document.createElement('button')
  document.body.append(anchor)
  const open = ref(true), root = document.createElement('div')
  document.body.append(root)
  const app = createApp({render: () => h(UiMenu, {
    open: open.value, anchor, items, 'onUpdate:open': (value: boolean) => { open.value = value },
  })})
  app.mount(root); mounted.push(app)
  return {open, anchor}
}
beforeEach(() => {
  vi.stubGlobal('matchMedia', () => ({matches: false}))
})
afterEach(() => {
  mounted.splice(0).forEach(app => app.unmount())
  document.body.innerHTML = ''
  vi.restoreAllMocks(); vi.unstubAllGlobals()
})

it('opens on the enabled checked item rather than a disabled selection', async () => {
  setupMenu([{id:'disabled',label:'Unavailable',checked:true,disabled:true,run:vi.fn()},
    {id:'enabled',label:'Ready',checked:true,run:vi.fn()}])
  await settle()
  expect(document.activeElement?.textContent).toContain('Ready')
})

it('keeps a mobile popover usable without automatically focusing an editable field', async () => {
  vi.stubGlobal('matchMedia', () => ({matches:true}))
  const root=document.createElement('div');document.body.append(root)
  const app=createApp({render:()=>h(UiPopover,{open:true,anchor:{x:12,y:24}},()=>h('input',{type:'text'}))})
  app.mount(root);mounted.push(app);await settle()
  expect(document.activeElement).toBe(document.querySelector('[data-ui-popover]'))
  expect(document.activeElement?.tagName).not.toBe('INPUT')
})

it('retains desktop first-field focus with preventScroll', async () => {
  const focus=vi.spyOn(HTMLElement.prototype,'focus'),root=document.createElement('div');document.body.append(root)
  const app=createApp({render:()=>h(UiPopover,{open:true,anchor:{x:12,y:24}},()=>h('input',{type:'text'}))})
  app.mount(root);mounted.push(app);await settle()
  expect(document.activeElement?.tagName).toBe('INPUT')
  expect(focus).toHaveBeenLastCalledWith({preventScroll:true})
})

it('does not install listeners for an opening cancelled during DOM mounting', async () => {
  const open=ref(true),close=vi.fn(),root=document.createElement('div');document.body.append(root)
  const app=createApp({render:()=>h(UiPopover,{open:open.value,anchor:{x:12,y:24},onClose:close},
    ()=>h('button',{onVnodeMounted:()=>{open.value=false}},'Cancel immediately'))})
  app.mount(root);mounted.push(app);await settle()
  document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))
  expect(close).not.toHaveBeenCalled()
  expect(document.querySelector('[data-ui-popover]')).toBeNull()
})

it('returns focus before a menu action so a newly opened field can own focus', async () => {
  const destination=document.createElement('input');document.body.append(destination)
  let focusedDuringAction:Element|null=null
  const {anchor,open}=setupMenu([{id:'settings',label:'Settings',run:()=>{
    focusedDuringAction=document.activeElement;destination.focus()
  }}])
  await settle();(document.querySelector('[role="menuitem"]') as HTMLButtonElement).click();await settle()
  expect(open.value).toBe(false);expect(focusedDuringAction).toBe(anchor)
  expect(document.activeElement).toBe(destination)
})

it('supports arrow navigation past disabled items and Escape back to its trigger', async () => {
  const {anchor,open}=setupMenu([{id:'first',label:'First',run:vi.fn()},
    {id:'disabled',label:'Disabled',disabled:true,run:vi.fn()}, {id:'last',label:'Last',run:vi.fn()}])
  await settle()
  document.activeElement?.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowDown',bubbles:true,cancelable:true}))
  expect(document.activeElement?.textContent).toContain('Last')
  document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true}));await settle()
  expect(open.value).toBe(false);expect(document.activeElement).toBe(anchor)
})
