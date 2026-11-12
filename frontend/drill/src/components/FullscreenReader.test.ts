// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { createApp, h, nextTick, reactive, type App } from 'vue'
import FullscreenReader from './FullscreenReader.vue'
import { uiLanguage } from '../lib/uiPreferences'
let app: App | undefined
let host: HTMLElement
const flush = async () => { await nextTick(); await nextTick() }
afterEach(() => { app?.unmount(); host?.remove(); document.body.style.overflow = ''; vi.restoreAllMocks() })
async function mount(prepare?: () => Promise<void>) {
  uiLanguage.value = 'en'
  host = document.createElement('div'); document.body.append(host)
  const opened = vi.fn()
  app = createApp(FullscreenReader, { title: 'Question', prepare, images: [{ src: '/first', width: 600, height: 900 }, { src: '/second', width: 600, height: 900 }], onOpened: opened })
  app.mount(host); await flush()
  const dialog = document.querySelector<HTMLDialogElement>('.fullscreen-reader')!
  dialog.showModal = function () { this.open = true }
  dialog.close = function () { this.open = false; this.dispatchEvent(new Event('close')) }
  return { dialog, opened }
}
it('opens a modal with ordered pages, locks background scrolling and restores it on close', async () => {
  const { dialog, opened } = await mount()
  document.body.style.overflow = 'clip'
  expect(dialog.querySelectorAll('img')).toHaveLength(0)
  host.querySelector('button')!.click(); await flush()
  expect(dialog.open).toBe(true)
  expect(opened).toHaveBeenCalledOnce()
  expect(document.body.style.overflow).toBe('hidden')
  expect([...dialog.querySelectorAll('img')].map(i => i.getAttribute('src'))).toEqual(['/first', '/second'])
  expect(dialog.textContent).toContain('scroll down to continue')
  dialog.querySelector<HTMLButtonElement>('.reader-close')!.click(); await flush()
  expect(dialog.open).toBe(false)
  expect(document.body.style.overflow).toBe('clip')
  expect(dialog.querySelectorAll('img')).toHaveLength(0)
})
it('supports zoom, image retry, live language changes and cleanup during navigation', async () => {
  const { dialog } = await mount()
  host.querySelector('button')!.click(); await flush()
  dialog.querySelector('img')!.dispatchEvent(new MouseEvent('dblclick', { bubbles: true })); await flush()
  expect(dialog.querySelector<HTMLElement>('.reader-document')!.style.width).toBe('100%')
  dialog.querySelector<HTMLButtonElement>('[aria-label="Zoom in"]')!.click(); await flush()
  expect(dialog.querySelector<HTMLElement>('.reader-document')!.style.width).toBe('125%')
  dialog.querySelector('img')!.dispatchEvent(new Event('error')); await flush()
  dialog.querySelector<HTMLButtonElement>('.reader-retry')!.click(); await flush()
  expect(dialog.querySelector('img')!.getAttribute('src')).toBe('/first?reader_retry=1')
  uiLanguage.value = 'zh-CN'; await flush()
  expect(dialog.querySelector('[aria-label="关闭全屏"]')).not.toBeNull()
  app!.unmount(); app = undefined
  expect(document.body.style.overflow).toBe('')
  expect(document.querySelector('.fullscreen-reader')).toBeNull()
})

it('allows a failed lazy load to retry while the close control remains usable', async () => {
  const prepare = vi.fn().mockRejectedValueOnce(new Error('Offline')).mockResolvedValueOnce(undefined)
  const { dialog } = await mount(prepare)
  host.querySelector('button')!.click(); await flush()
  expect(dialog.querySelector('[role="alert"]')?.textContent).toContain('Offline')
  expect(dialog.querySelector('.reader-close')).not.toBeNull()
  dialog.querySelector<HTMLButtonElement>('.reader-load-retry')!.click(); await flush()
  expect(prepare).toHaveBeenCalledTimes(2)
  expect(dialog.querySelector('[role="alert"]')).toBeNull()
})

it('replaces content inside the same open dialog without reopening or unlocking the page', async () => {
  const props = reactive({ title: 'First', contentKey: 'q1', images: [{ src: '/first', width: 600, height: 900 }] })
  host = document.createElement('div'); document.body.append(host)
  app = createApp({ render: () => h(FullscreenReader, props) }); app.mount(host); await flush()
  const dialog = document.querySelector<HTMLDialogElement>('.fullscreen-reader')!
  const show = vi.fn(function (this: HTMLDialogElement) { this.open = true })
  const close = vi.fn(function (this: HTMLDialogElement) { this.open = false })
  dialog.showModal = show; dialog.close = close
  host.querySelector('button')!.click(); await flush()
  props.title = 'Second'; props.contentKey = 'q2'; props.images = [{ src: '/second', width: 600, height: 900 }]; await flush()
  expect(document.querySelector('.fullscreen-reader')).toBe(dialog)
  expect(dialog.open).toBe(true)
  expect(dialog.getAttribute('aria-label')).toBe('Second')
  expect(dialog.querySelector('img')!.getAttribute('src')).toBe('/second')
  expect(show).toHaveBeenCalledTimes(1)
  expect(close).not.toHaveBeenCalled()
  expect(document.body.style.overflow).toBe('hidden')
})
it('exposes recovery actions inside the open modal without changing ordinary toolbar controls',async()=>{
  host=document.createElement('div');document.body.append(host)
  const reconnect=vi.fn(),skip=vi.fn()
  const issue=reactive({visible:false})
  app=createApp({render:()=>h(FullscreenReader,{title:'Question',images:[{src:'/first',width:600,height:900}]},{recovery:()=>issue.visible?h('div',{class:'test-recovery'},[
    h('button',{onClick:reconnect},'Reconnect timer'),h('button',{onClick:skip},'Save without duration'),
  ]):null})})
  app.mount(host);await flush()
  const dialog=document.querySelector<HTMLDialogElement>('.fullscreen-reader')!
  dialog.showModal=function(){this.open=true};dialog.close=function(){this.open=false;this.dispatchEvent(new Event('close'))}
  host.querySelector('button')!.click();await flush()
  expect(dialog.querySelector('.test-recovery')).toBeNull()
  const ordinaryButtons=dialog.querySelectorAll('.reader-toolbar button').length
  issue.visible=true;await flush()
  const buttons=dialog.querySelectorAll<HTMLButtonElement>('.test-recovery button')
  expect(buttons).toHaveLength(2);buttons[0]!.click();buttons[1]!.click()
  expect(reconnect).toHaveBeenCalledOnce();expect(skip).toHaveBeenCalledOnce()
  expect(dialog.open).toBe(true)
  expect(dialog.querySelectorAll('.reader-toolbar button')).toHaveLength(ordinaryButtons)
})

it('keeps modal overlays inside the native dialog and returns focus to the original trigger', async () => {
  const { dialog } = await mount()
  const trigger = host.querySelector<HTMLButtonElement>('button')!
  trigger.focus(); trigger.click(); await flush()
  expect(dialog.querySelector('[data-overlay-host]')).not.toBeNull()
  expect(dialog.querySelector('[aria-label="Fit to width"]')).not.toBeNull()
  dialog.querySelector<HTMLButtonElement>('.reader-close')!.click(); await flush()
  expect(document.activeElement).toBe(trigger)
})
