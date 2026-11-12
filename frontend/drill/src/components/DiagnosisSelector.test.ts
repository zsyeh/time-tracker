// @vitest-environment jsdom
import { bindTestPreferences, clearTestPreferences } from '../../../shared/preferences/testSupport'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, h, nextTick, reactive, type App } from 'vue'
import DiagnosisSelector from './DiagnosisSelector.vue'
import type { ErrorCode } from '../types'
import { uiLanguage } from '../lib/uiPreferences'

let app: App | undefined
let host: HTMLElement
beforeEach(async () => { localStorage.clear(); await bindTestPreferences('zh-CN') })
afterEach(() => { app?.unmount(); host?.remove(); clearTestPreferences() })
const options = [
  { code: 'A' as const, label: '知识断层', group: 'A' },
  { code: 'B1' as const, label: '想不起来', group: 'B' },
  { code: 'B2' as const, label: '不会启动', group: 'B' },
  { code: 'B3' as const, label: '不会组合', group: 'B' },
  { code: 'C1' as const, label: '计算错误', group: 'C' },
  { code: 'C2' as const, label: '符号/方向/单位', group: 'C' },
  { code: 'C3' as const, label: '边界/条件错误', group: 'C' },
  { code: 'D' as const, label: '看解析仍不懂', group: 'D' },
]
it('keeps all eight diagnoses one click away and delegates changes without changing the controlled draft', async () => {
  uiLanguage.value = 'zh-CN'
  const props = reactive({ modelValue: ['B2', 'A'] as ErrorCode[], primary: 'B2' as ErrorCode | null, options, disabled: false })
  const toggle = vi.fn()
  host = document.createElement('div'); document.body.append(host)
  app = createApp({ render: () => h(DiagnosisSelector, { ...props, onToggle: toggle }) }); app.mount(host); await nextTick()
  const inputs = [...host.querySelectorAll<HTMLInputElement>('input')]
  expect(inputs.map(item => item.value)).toEqual(['A', 'B1', 'B2', 'B3', 'C1', 'C2', 'C3', 'D'])
  expect(host.querySelectorAll('fieldset')).toHaveLength(4)
  expect(inputs.find(item => item.value === 'B2')?.getAttribute('aria-label')).toContain('主要原因')
  host.querySelector<HTMLLabelElement>('label')!.click(); await nextTick()
  expect(toggle).toHaveBeenCalledOnce(); expect(toggle).toHaveBeenLastCalledWith('A')
  expect(props.modelValue).toEqual(['B2', 'A'])
  expect(props.primary).toBe('B2')
  props.modelValue = ['B2']; await nextTick()
  expect(inputs[0]!.checked).toBe(false)
  props.disabled = true; await nextTick()
  host.querySelector<HTMLLabelElement>('label')!.click()
  expect(toggle).toHaveBeenCalledTimes(1)
})

it('keeps all eight one-click choices in the compact pane without extra disclosures', async () => {
  const toggle = vi.fn()
  host = document.createElement('div'); document.body.append(host)
  app = createApp({ render: () => h(DiagnosisSelector, { modelValue: ['B2'], primary: 'B2', options, compact: true, onToggle: toggle }) }); app.mount(host); await nextTick()
  expect(host.querySelectorAll('fieldset')).toHaveLength(1)
  expect(host.querySelectorAll('input[type=checkbox]')).toHaveLength(8)
  expect(host.querySelector('details')).toBeNull()
  host.querySelectorAll('label')[6]!.click(); await nextTick()
  expect(toggle).toHaveBeenLastCalledWith('C3')
  expect(host.querySelector('input[value=B2]')?.getAttribute('aria-label')).toContain('主要原因')
})
