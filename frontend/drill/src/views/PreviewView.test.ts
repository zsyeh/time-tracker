// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, h, nextTick, type App } from 'vue'
import { createMemoryHistory, createRouter, RouterView } from 'vue-router'
import PreviewView from './PreviewView.vue'
import { accountPreferences } from '../../../shared/preferences/store'
const f=vi.hoisted(()=>({load:vi.fn(),get:vi.fn(),abort:vi.fn(),save:vi.fn(),saved:vi.fn(),capture:vi.fn(),restore:vi.fn(),jump:vi.fn()}))
const question={entry_id:'attempt:9',question_uuid:'uuid-1',index:14,label:'同题第2次作答',document:'Book',topic:'Topic',state:'review',preview:{question_markdown:'题干',assets:[]}}
const anchor={...question,offset:-31,collection_version:'v1'}
const context={version:1,workspace:'drill',source:'attempts',query:{q:'导数',sort:'recent'},returnTo:'/insight?attempt_page=3&q=导数'}
vi.mock('../lib/collectionPreview',()=>({getPreviewSession:()=>({count:10000,version:'v1',get:f.get,load:f.load,abort:f.abort}),getPreviewAnchor:f.saved,savePreviewAnchor:f.save}))
vi.mock('../../../shared/preferences/store',async()=>({accountPreferences:{userId:(await import('vue')).ref('42')}}))
vi.mock('../components/preview/VirtualPreviewList.vue',async()=>{
 const {defineComponent,h}=await import('vue')
 return{default:defineComponent({props:['count','getItem'],emits:['open','anchor'],setup(props,{emit,expose}){expose({captureAnchor:f.capture,restoreAnchor:f.restore,scrollToIndex:f.jump});return()=>h('button',{'data-open':'',onClick:()=>emit('open',props.getItem(14))},'进入做题')}})}
})
vi.mock('../components/FullscreenReader.vue',()=>({default:{template:'<div />'}}))
let app:App|undefined,host:HTMLDivElement
beforeEach(()=>{vi.clearAllMocks();accountPreferences.userId.value='42';f.get.mockReturnValue(question);f.saved.mockReturnValue(anchor);f.capture.mockReturnValue(anchor);f.load.mockResolvedValue({count:10000,collection_version:'v1',located:question,results:[question]});host=document.createElement('div');document.body.append(host)})
afterEach(()=>{app?.unmount();app=undefined;host.remove()})
async function settle(){await nextTick();await Promise.resolve();await nextTick();await Promise.resolve();await nextTick()}
async function mount(extra:Record<string,string>={}){
 const router=createRouter({history:createMemoryHistory(),routes:[{path:'/preview',component:PreviewView},{path:'/practice/:uuid',component:{template:'<div />'}},{path:'/insight',component:{template:'<div />'}}]})
 await router.push({path:'/preview',query:{list:JSON.stringify(context),...extra}});await router.isReady();app=createApp({render:()=>h(RouterView)});app.use(router).mount(host);await settle();return router
}
it('revalidates a returned collection with its saved entry/index and measured offset',async()=>{
 await mount();expect(f.load).toHaveBeenCalledWith(expect.objectContaining({locate_entry:'attempt:9',fallback_index:14,fresh:true}))
 expect(f.restore).toHaveBeenCalledWith(expect.objectContaining({entry_id:'attempt:9',index:14,offset:-31}))
})
it('lets an explicit fresh origin override a saved location',async()=>{
 await mount({entry:'attempt:99',question:'uuid-7'});expect(f.load).toHaveBeenCalledWith(expect.objectContaining({locate_entry:'attempt:99',locate_uuid:'uuid-7'}))
})
it('saves the original browsing anchor and preserves exact Attempt entry on entering practice',async()=>{
 const router=await mount();host.querySelector<HTMLButtonElement>('[data-open]')!.click();await settle();await vi.waitFor(()=>expect(router.currentRoute.value.path).toBe('/practice/uuid-1'))
 expect(router.currentRoute.value.path).toBe('/practice/uuid-1');expect(router.currentRoute.value.query.entry).toBe('attempt:9');expect(router.currentRoute.value.query.from).toBe('preview')
 expect(f.save).toHaveBeenCalledWith(expect.objectContaining({source:'attempts',query:context.query}),expect.objectContaining({offset:-31,index:14}))
})
it('loads the absolute position in batches instead of requiring all preceding metadata',async()=>{
 await mount();const input=host.querySelector<HTMLInputElement>('#preview-position')!;input.value='5001';input.dispatchEvent(new Event('input',{bubbles:true}));host.querySelector('form')!.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));await settle()
 expect(f.load).toHaveBeenLastCalledWith({offset:5000});expect(f.jump).toHaveBeenCalledWith(5000)
})
it('refreshes changed learning state without discarding the saved browsing position',async()=>{
 await mount();f.load.mockClear();window.dispatchEvent(new CustomEvent('drill:question-state-changed'));await settle();expect(f.load).toHaveBeenCalledWith(expect.objectContaining({fresh:true,locate_entry:'attempt:9',fallback_index:14}))
})
it('clears private content and aborts work immediately after the account changes',async()=>{
 await mount();accountPreferences.userId.value='99';await settle();expect(f.abort).toHaveBeenCalled();expect(host.querySelector('[data-open]')).toBeNull();expect(host.textContent).toContain('账号已变化')
})
it('rejects malformed list context without issuing a collection query',async()=>{
 const router=createRouter({history:createMemoryHistory(),routes:[{path:'/preview',component:PreviewView}]});await router.push('/preview?list=broken');await router.isReady();app=createApp({render:()=>h(RouterView)});app.use(router).mount(host);await settle()
 expect(f.load).not.toHaveBeenCalled();expect(host.textContent).toContain('上下文无效')
})
it('stores the departing context anchor under the old context before a new context loads',async()=>{
 const router=await mount();f.save.mockClear();f.load.mockImplementationOnce(()=>new Promise(()=>{}))
 const next={...context,source:'notes',returnTo:'/insight?note_page=2'}
 await router.push({path:'/preview',query:{list:JSON.stringify(next)}});await settle()
 expect(f.save).toHaveBeenCalledWith(expect.objectContaining({source:'attempts'}),expect.objectContaining({index:14}))
 expect(f.save.mock.calls.some(call=>call[0].source==='notes')).toBe(false)
})
it('does not surface an obsolete position-request error after changing collections',async()=>{
 const router=await mount();let reject!: (error:Error)=>void;f.load.mockImplementationOnce(()=>new Promise((_resolve,no)=>{reject=no}))
 const input=host.querySelector<HTMLInputElement>('#preview-position')!;input.value='5001';input.dispatchEvent(new Event('input',{bubbles:true}));host.querySelector('form')!.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));await settle()
 await router.push({path:'/preview',query:{list:JSON.stringify({...context,source:'notes'})}});await settle();reject(new Error('obsolete position failure'));await settle()
 expect(host.textContent).not.toContain('obsolete position failure')
})
it('consumes an initial deep-link entry before opening another question so browser Back restores the newer anchor',async()=>{
 const origin={...question,entry_id:'attempt:1',question_uuid:'uuid-origin',index:2}
 f.load.mockResolvedValueOnce({count:10000,collection_version:'v1',located:origin,results:[origin]})
 f.saved.mockImplementation(()=>f.save.mock.calls.at(-1)?.[1] ?? anchor)
 const router=await mount({entry:origin.entry_id,question:origin.question_uuid})
 expect(f.restore).toHaveBeenCalledWith(expect.objectContaining({entry_id:origin.entry_id,index:2,offset:0}))
 f.capture.mockReturnValue(anchor);host.querySelector<HTMLButtonElement>('[data-open]')!.click()
 await vi.waitFor(()=>expect(router.currentRoute.value.path).toBe('/practice/uuid-1'))
 expect(router.currentRoute.value.query.entry).toBe('attempt:9')
 f.load.mockClear();router.back()
 await vi.waitFor(()=>expect(router.currentRoute.value.path).toBe('/preview'));await settle()
 expect(router.currentRoute.value.query.entry).toBeUndefined();expect(router.currentRoute.value.query.question).toBeUndefined()
 expect(f.load).toHaveBeenCalledWith(expect.objectContaining({locate_entry:'attempt:9',fallback_index:14}))
 expect(f.restore).toHaveBeenLastCalledWith(expect.objectContaining({entry_id:'attempt:9',index:14,offset:-31}))
})
it('does not let a slower earlier absolute-position request overwrite a newer jump',async()=>{
 await mount();let first!: (page:unknown)=>void,second!: (page:unknown)=>void
 f.load.mockImplementationOnce(()=>new Promise(resolve=>{first=resolve})).mockImplementationOnce(()=>new Promise(resolve=>{second=resolve}))
 const input=host.querySelector<HTMLInputElement>('#preview-position')!,form=host.querySelector('form')!
 input.value='5001';input.dispatchEvent(new Event('input',{bubbles:true}));form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));await settle()
 input.value='6001';input.dispatchEvent(new Event('input',{bubbles:true}));form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));await settle()
 second({count:10000,results:[]});await settle();expect(f.jump).toHaveBeenLastCalledWith(6000)
 first({count:10000,results:[]});await settle();expect(f.jump).not.toHaveBeenCalledWith(5000)
})
it.each([
 ['PAPER_REVISION_PREVIEW_CANONICAL_PRACTICE_IS_SEPARATE','不会修改这份试卷'],
 ['ENTRY_REMOVED_USING_NEAREST','已定位到附近题目'],
])('translates the %s transport notice into a clear user-facing explanation',async(notice,explanation)=>{
 f.load.mockResolvedValueOnce({count:10000,collection_version:'v1',located:question,results:[question],notice});await mount()
 expect(host.textContent).toContain(explanation);expect(host.textContent).not.toContain(notice)
})
