// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { usePracticeQuery } from './usePracticeQuery'
let app: App | undefined
let host: HTMLDivElement
beforeEach(() => { vi.useFakeTimers(); host = document.createElement('div'); document.body.append(host) })
afterEach(() => { app?.unmount(); app = undefined; host.remove(); vi.useRealTimers() })
async function mount(url = '/practice') {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/practice', component: { template: '<div />' } }] })
  await router.push(url); await router.isReady()
  const invalidate = vi.fn()
  let state!: ReturnType<typeof usePracticeQuery>
  app = createApp({ setup() { state = usePracticeQuery(invalidate); return () => null } })
  app.use(router).mount(host)
  return { router, state, invalidate }
}
async function flush() { await Promise.resolve(); await nextTick(); await Promise.resolve(); await nextTick() }
it('invalidates an old request immediately but commits one IME query after composition ends', async () => {
  const { router, state, invalidate } = await mount('/practice?document=2')
  state.compositionStart(); state.draft.value = '偏'; state.input()
  await vi.advanceTimersByTimeAsync(400)
  expect(router.currentRoute.value.query.q).toBeUndefined()
  expect(invalidate).toHaveBeenCalled()
  state.draft.value = '偏导数'; state.compositionEnd()
  await vi.advanceTimersByTimeAsync(249)
  expect(router.currentRoute.value.query.q).toBeUndefined()
  await vi.advanceTimersByTimeAsync(1); await flush()
  expect(router.currentRoute.value.query).toEqual({ document: '2', q: '偏导数' })
})
it('batches related filters into one history update, resets page and retains scope', async () => {
  const { router, state } = await mount('/practice?collection=math2_selected&page=3&topic=5')
  const push = vi.spyOn(router, 'push')
  state.apply({ document: '2', topic: '' }); state.apply({ status: 'unattempted' })
  await flush()
  expect(push).toHaveBeenCalledTimes(1)
  await vi.waitFor(() => expect(router.currentRoute.value.query).toEqual({ collection: 'math2_selected', document: '2', status: 'unattempted' }))
})
it('restores the input on browser navigation and preserves explicit pagination', async () => {
  const { router, state } = await mount('/practice?q=导数')
  state.apply({ page: '4' }, 'push', false); await flush()
  await vi.waitFor(() => expect(router.currentRoute.value.query.page).toBe('4'))
  await router.push('/practice?q=Fourier&page=2'); await flush()
  expect(state.draft.value).toBe('Fourier')
  expect(state.applied.value.page).toBe('2')
})

it('never commits a pending input into a destination question route', async () => {
  const { router, state } = await mount('/practice?q=导数')
  router.addRoute({ path: '/practice/:uuid', component: { template: '<div />' } })
  state.draft.value = '偏导数'; state.input()
  await router.push('/practice/real-question?q=导数&practice_page=2')
  await vi.advanceTimersByTimeAsync(500); await flush()
  expect(router.currentRoute.value.path).toBe('/practice/real-question')
  expect(router.currentRoute.value.query).toEqual({ q: '导数', practice_page: '2' })
})
it('drops an already queued query when its view is disposed', async () => {
  const { router, state } = await mount('/practice?q=导数')
  const replace = vi.spyOn(router, 'replace')
  state.apply({ q: '偏导数' }, 'replace')
  app!.unmount(); app = undefined
  await flush()
  expect(replace).not.toHaveBeenCalled()
})
