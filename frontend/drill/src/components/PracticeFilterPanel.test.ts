// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { createApp, h, nextTick, ref, type App } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import PracticeFilterPanel from './PracticeFilterPanel.vue'
import type { PracticeQuery } from '../../../shared/search/queryState'
const catalog = { summary: { categories: [] }, documents: [{ id: 1, title: 'A', question_count: 1 }, { id: 2, title: 'B', question_count: 1 }], topics: [{ id: 3, document_id: 1, path: 'Topic A', question_count: 1 }, { id: 4, document_id: 2, path: 'Topic B', question_count: 1 }] }
let app: App | undefined
let host: HTMLDivElement
let anchor: HTMLButtonElement
afterEach(() => { app?.unmount(); app = undefined; host?.remove(); anchor?.remove(); vi.restoreAllMocks() })
it('applies selections immediately, clears an incompatible topic and closes without undoing', async () => {
 host = document.createElement('div'); document.body.append(host); anchor = document.createElement('button'); document.body.append(anchor)
 HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', '') }
 HTMLDialogElement.prototype.close = function () { this.removeAttribute('open') }
 const focus = vi.spyOn(anchor, 'focus')
 const model = ref<PracticeQuery>({ collection: 'math2_selected', q: '导数', document: '1', topic: '3' })
 const opened = ref(true)
 const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/practice', component: { template: '<div />' } }] }); await router.push('/practice'); await router.isReady()
 app = createApp({ setup() { return () => h(PracticeFilterPanel, { open: opened.value, anchor, modelValue: model.value, catalog: catalog as never, 'onUpdate:modelValue': (value: PracticeQuery) => { model.value = value }, 'onUpdate:open': (value: boolean) => { opened.value = value } }) } })
 app.use(router).mount(host); await nextTick(); await nextTick()
 expect(host.querySelector('dialog')?.open).toBe(true)
 const documentSelect = host.querySelectorAll<HTMLSelectElement>('select')[1]!
 documentSelect.value = '2'; documentSelect.dispatchEvent(new Event('change', { bubbles: true })); await nextTick()
 expect(model.value).toMatchObject({ document: '2', topic: '', collection: 'math2_selected', q: '导数' })
 host.querySelector('dialog')!.dispatchEvent(new Event('cancel', { cancelable: true })); await nextTick(); await nextTick()
 expect(opened.value).toBe(false)
 expect(model.value.document).toBe('2')
 expect(focus).toHaveBeenCalled()
})
