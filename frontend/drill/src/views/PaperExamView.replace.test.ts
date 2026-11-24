// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, defineComponent, h, nextTick, type App } from 'vue'
import PaperExamView from './PaperExamView.vue'
import { api } from '../lib/api'

const replaceRoute = vi.hoisted(() => ({ query: { position: '2' } }))
vi.mock('vue-router', () => ({ useRoute: () => replaceRoute, useRouter: () => ({ replace: vi.fn() }) }))
vi.mock('../lib/api', () => ({ api: vi.fn(), ApiError: class extends Error {} }))
vi.mock('../lib/workspace', () => ({ patchQuestionState: vi.fn() }))
vi.mock('../lib/share', () => ({ createAndCopyShare: vi.fn() }))
vi.mock('../lib/runtimePath', () => ({ withWorkspacePrefix: (path: string) => path }))
vi.mock('../lib/listContext', () => ({ buildListContext: () => ({}), previewLocation: () => '/preview', previewQuestionLocation: () => '/practice' }))
vi.mock('../components/PaperQuestionContent.vue', () => ({ default: defineComponent({ props: ['question'], setup: props => () => h('div', { class: 'test-question' }, props.question.uuid) }) }))
vi.mock('../components/FullscreenReader.vue', () => ({ default: defineComponent({
  props: ['contentKey'],
  setup: (props, { slots }) => () => h('aside', { class: 'test-reader', 'data-content-key': props.contentKey }, [slots.actions?.(), slots.recovery?.()]),
}) }))
let app: App | undefined
let host: HTMLDivElement
function paper(question = 'old-2', note = '原备注') {
  return {
    uuid: 'paper-1', title: '考试', status: 'completed', started_at: new Date().toISOString(), duration_minutes: 180,
    items: [1, 2, 3].map(position => ({ position, user_answer: position === 2 ? note : '', self_score: position === 2 ? 3 : null,
      question: { uuid: position === 2 ? question : `old-${position}`, question_assets: [], answer_assets: [], document: '题册' },
    })),
  }
}
function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>(done => { resolve = done })
  return { promise, resolve }
}
async function settle() { for (let i = 0; i < 8; i++) { await Promise.resolve(); await nextTick() } }
function button(text: string, root: ParentNode = host) {
  return [...root.querySelectorAll<HTMLButtonElement>('button')].find(entry => entry.textContent === text)!
}
async function mount() {
  host = document.createElement('div'); document.body.append(host)
  app = createApp(PaperExamView, { uuid: 'paper-1' })
  app.component('RouterLink', defineComponent({ props: ['to'], setup: (props, { attrs, slots }) => () => h('a', { href: props.to, ...attrs }, slots.default?.()) }))
  app.mount(host); await settle()
}
beforeEach(() => {
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  vi.mocked(api).mockImplementation(async path => path.endsWith('/review/') ? paper() : undefined)
})
afterEach(async () => { app?.unmount(); await settle(); host?.remove(); app = undefined; vi.restoreAllMocks(); vi.clearAllMocks() })

it('flushes queued notes, blocks edits and navigation, then refreshes the same position with answers hidden', async () => {
  const firstSave = deferred<unknown>()
  const replacement = deferred<unknown>()
  let patches = 0
  vi.mocked(api).mockImplementation(async (path, options) => {
    if (path.endsWith('/review/')) return paper()
    if (options?.method === 'PATCH') { patches++; return patches === 1 ? firstSave.promise : undefined }
    return replacement.promise
  })
  await mount()
  button('查看答案').click(); await settle()
  const textarea = host.querySelector('textarea')!
  textarea.value = '第一版'; textarea.dispatchEvent(new Event('input')); textarea.dispatchEvent(new Event('blur')); await settle()
  textarea.value = '最终备注'; textarea.dispatchEvent(new Event('input'))
  button('更换本题').click(); await settle()
  expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining('掌握状态、收藏和作答历史保持不变'))
  expect(textarea.disabled).toBe(true)
  expect(button('下一题').disabled).toBe(true)
  expect(button('更换中…').disabled).toBe(true)
  expect(vi.mocked(api).mock.calls.some(([path]) => path.endsWith('/replace/'))).toBe(false)
  textarea.dispatchEvent(new Event('blur'))
  firstSave.resolve(undefined); await settle()
  const calls = vi.mocked(api).mock.calls
  expect(calls.filter(([, options]) => options?.method === 'PATCH')).toHaveLength(2)
  expect(calls.find(([path]) => path.endsWith('/replace/'))).toEqual([
    '/api/drill/papers/paper-1/items/2/replace/', { method: 'POST', body: JSON.stringify({ expected_question_uuid: 'old-2' }) },
  ])
  expect(calls.filter(([, options]) => options?.method === 'PATCH')[1]![1]?.body).toBe(JSON.stringify({ user_answer: '最终备注', expected_question_uuid: 'old-2' }))
  replacement.resolve(paper('new-2', '')); await settle()
  expect(host.querySelector('.question-heading')?.textContent).toContain('第 2 / 3 题')
  expect(host.querySelector('.test-question')?.textContent).toBe('new-2')
  expect(host.querySelector('textarea')?.value).toBe('')
  expect(button('查看答案')).toBeTruthy()
  expect(host.querySelector('.test-reader')?.getAttribute('data-content-key')).toBe('new-2-false')
  expect(button('下一题').disabled).toBe(false)
  expect(calls.some(([path]) => /attempt|clipboard|share/.test(path))).toBe(false)
})

it('keeps the original question and note after a conflict and permits retry from fullscreen', async () => {
  let replacements = 0
  vi.mocked(api).mockImplementation(async (path, options) => {
    if (path.endsWith('/review/')) return paper()
    if (options?.method === 'PATCH') return undefined
    if (++replacements === 1) throw new Error('已分享的套卷不能更换题目')
    return paper('new-2', '')
  })
  await mount()
  const reader = host.querySelector('.test-reader')!
  button('更换本题', reader).click(); await settle()
  expect(reader.textContent).toContain('已分享的套卷不能更换题目')
  expect(host.querySelector('.test-question')?.textContent).toBe('old-2')
  expect(host.querySelector('textarea')?.value).toBe('原备注')
  expect(button('更换本题', reader).disabled).toBe(false)
  button('更换本题', reader).click(); await settle()
  expect(host.querySelector('.test-question')?.textContent).toBe('new-2')
  expect(reader.querySelector('[role="alert"]')).toBeNull()
})

it('aborts replacement on save failure and leaves the note editable', async () => {
  vi.mocked(api).mockImplementation(async path => {
    if (path.endsWith('/review/')) return paper()
    throw new Error('网络错误')
  })
  await mount(); button('更换本题').click(); await settle()
  expect(vi.mocked(api).mock.calls.some(([path]) => path.endsWith('/replace/'))).toBe(false)
  expect(host.textContent).toContain('备注未保存')
  expect(host.querySelector('textarea')?.disabled).toBe(false)
})

it('does not save or replace when confirmation is cancelled', async () => {
  vi.mocked(window.confirm).mockReturnValue(false)
  await mount(); button('更换本题').click(); await settle()
  expect(vi.mocked(api).mock.calls).toHaveLength(1)
  expect(host.querySelector('.test-question')?.textContent).toBe('old-2')
})

it('blocks the answer shortcut and ordinary answer button before the exam ends', async () => {
  vi.mocked(api).mockImplementation(async path => path.endsWith('/review/') ? { ...paper(), status:'in_progress' } : undefined)
  await mount()
  document.dispatchEvent(new KeyboardEvent('keydown',{key:'a',bubbles:true,cancelable:true}));await settle()
  expect(host.textContent).toContain('考试未结束')
  expect(host.querySelector('.training-answer')).toBeNull()
  expect(button('查看答案')?.disabled).toBe(true)
})
