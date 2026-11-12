// @vitest-environment jsdom
import { bindTestPreferences, clearTestPreferences } from '../../../shared/preferences/testSupport'
import { afterEach, beforeEach, expect, it } from 'vitest'
import { createApp, h, nextTick, reactive, type App } from 'vue'
import NoteVisibility from './NoteVisibility.vue'
import { uiLanguage } from '../lib/uiPreferences'
import { uiText } from '../lib/uiText'

let app: App | undefined
let host: HTMLDivElement
beforeEach(async () => { localStorage.clear(); await bindTestPreferences() })
afterEach(() => { app?.unmount(); host?.remove(); clearTestPreferences() })
async function mount(note = '私人笔记，不要翻译', questionKey = 'q1') {
  const props = reactive({ note, questionKey })
  host = document.createElement('div'); document.body.append(host)
  app = createApp({ render: () => h(NoteVisibility, props, { default: () => h('textarea', { value: props.note }) }) })
  app.mount(host); await nextTick()
  return props
}
async function toggle() { host.querySelector<HTMLInputElement>('input')!.click(); await nextTick() }
it('defaults to the existing note UI, hides content, and reveals with one click', async () => {
  const props = await mount()
  expect(host.querySelector('textarea')?.value).toBe(props.note)
  await toggle()
  expect(host.querySelector('textarea')).toBeNull()
  expect(host.textContent).toContain('Note hidden · click to show')
  expect(host.textContent).not.toContain(props.note)
  host.querySelector<HTMLButtonElement>('.note-hidden')!.click(); await nextTick()
  expect(host.querySelector('textarea')?.value).toBe(props.note)
  props.questionKey = 'q2'; props.note = '第二题笔记'; await nextTick()
  expect(host.querySelector('textarea')).toBeNull()
  await toggle()
  expect(host.querySelector('textarea')?.value).toBe('第二题笔记')
})
it('keeps empty notes editable and does not hide the first typed character', async () => {
  const props = await mount('')
  await toggle()
  expect(host.querySelector('.note-hidden')).toBeNull()
  host.querySelector('textarea')!.focus()
  props.note = 'first character'; await nextTick()
  expect(host.querySelector('textarea')).not.toBeNull()
  expect(props.note).toBe('first character')
})
it('remembers the preference after remounting and translates live without altering the note', async () => {
  await mount(); await toggle()
  app!.unmount(); host.remove()
  const props = await mount()
  expect(host.querySelector<HTMLInputElement>('input')!.checked).toBe(true)
  uiLanguage.value = 'zh-CN'; await nextTick()
  expect(host.textContent).toContain('隐藏笔记')
  expect(host.textContent).toContain('笔记已隐藏 · 点击显示')
  uiLanguage.value = 'en'; await nextTick()
  expect(host.textContent).toContain('Hide notes')
  expect(props.note).toBe('私人笔记，不要翻译')
})
it('translates authored interface messages in both directions without changing arbitrary learning text', () => {
  expect(uiText('保存失败，本地草稿仍保留')).toBe('Save failed; local draft retained')
  expect(uiText('独立性未知')).toBe('Independence unknown')
  expect(uiText('我的笔记：保存失败')).toBe('我的笔记：保存失败')
  uiLanguage.value = 'zh-CN'
  expect(uiText('Copy share link')).toBe('复制分享链接')
})
