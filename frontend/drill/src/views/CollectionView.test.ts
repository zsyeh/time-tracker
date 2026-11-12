// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import CollectionView from './CollectionView.vue'
import { api } from '../lib/api'
vi.mock('../lib/api',()=>({api:vi.fn()}))
let app:App|undefined,host:HTMLDivElement
beforeEach(()=>{vi.clearAllMocks();host=document.createElement('div');document.body.append(host);vi.mocked(api).mockResolvedValue({count:50,next:'next',previous:'prev',results:[{uuid:'saved-question',display_label:'Saved question',question_order:1,document:'Book',topic:'Topic',state:'review',attempt_count:1,saved_note:''}]})})
afterEach(()=>{app?.unmount();host.remove()})
async function settle(){await nextTick();await Promise.resolve();await nextTick()}
async function mount(kind:'favorite'|'review_later'){
 const path=kind==='favorite'?'/favorites':'/review-later'
 const router=createRouter({history:createMemoryHistory(),routes:[{path,component:CollectionView},{path:'/preview',component:{template:'<div />'}},{path:'/practice/:uuid',component:{template:'<div />'}}]})
 await router.push(path+'?page=2');await router.isReady();app=createApp(CollectionView,{kind});app.use(router).mount(host);await settle();return router
}
it.each(['favorite','review_later']as const)('opens the complete %s collection in its own saved-order source rather than substituting Practice filters',async(kind)=>{
 const router=await mount(kind),returnTo=router.currentRoute.value.fullPath
 host.querySelector<HTMLButtonElement>('.preview-all')!.click();await vi.waitFor(()=>expect(router.currentRoute.value.path).toBe('/preview'))
 const location=router.currentRoute.value,context=JSON.parse(String(location.query.list))
 expect(location.path).toBe('/preview');expect(context).toMatchObject({source:kind,workspace:'drill',returnTo})
 expect(context.query).not.toHaveProperty('page');expect(context.query).not.toHaveProperty('favorite')
 expect(location.query.question).toBe('saved-question')
})
it('retains the direct question behavior and collection page when choosing an ordinary saved row',async()=>{
 const router=await mount('favorite')
 host.querySelector<HTMLButtonElement>('.question-row')!.click();await vi.waitFor(()=>expect(router.currentRoute.value.path).toBe('/practice/saved-question'))
 expect(router.currentRoute.value.path).toBe('/practice/saved-question')
 expect(router.currentRoute.value.query).toEqual({from:'collection',collection:'favorite',collection_page:'2'})
})
