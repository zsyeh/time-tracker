// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App, type Component } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import CircuitSelectedView from './CircuitSelectedView.vue'
import SignalSelectedView from './SignalSelectedView.vue'
import AnalogSelectedView from './AnalogSelectedView.vue'
import DigitalSelectedView from './DigitalSelectedView.vue'
import CommunicationSelectedView from './CommunicationSelectedView.vue'
import { api } from '../lib/api'
vi.mock('../lib/api',()=>({api:vi.fn()}))
vi.mock('../lib/runtimePath',()=>({runtimeWorkspace:'ei'}))
let app:App|undefined,host:HTMLDivElement
const progress={total:1,attempted:0,mastered:0,unattempted:1}
beforeEach(()=>{vi.clearAllMocks();host=document.createElement('div');document.body.append(host);vi.mocked(api).mockResolvedValue({title:'Selected',basis:'Synthetic',progress,selected_count:1,ready_count:1,inventory_count:1,review_count:0,excluded_count:0,review_items:[],groups:[{key:'chosen',title:'Chosen group',rank:1,tier:'core',focus:'Practice',progress,questions:[{uuid:'selected-question',label:'Selected question',book:'Book',bucket:'chosen',tier:'core',kind:'calculation',state:'unattempted',ready:true,combined:false,question_mode:'image',answer_mode:'image',scope_note:'',has_open_erratum:false,pdf_pages:null,tags:[],reason:[]}]}]})})
afterEach(()=>{app?.unmount();host.remove()})
it.each([
 ['circuit',CircuitSelectedView],['signal',SignalSelectedView],['analog',AnalogSelectedView],['digital',DigitalSelectedView],['communication',CommunicationSelectedView],
]as Array<[string,Component]>)('preserves the %s selected collection and every applied scope when opening its preview',async(course,view)=>{
 const path=`/${course}-selected`,router=createRouter({history:createMemoryHistory(),routes:[{path,component:view},{path:'/preview',component:{template:'<div />'}}]})
 await router.push(path+'?all=1&bucket=chosen&tier=core&kind=calculation&combined=1&state=review&type_group=small');await router.isReady()
 app=createApp(view);app.use(router).mount(host);await nextTick();await Promise.resolve();await nextTick()
 await vi.waitFor(()=>expect(host.querySelector<HTMLButtonElement>('.preview-all')!.disabled).toBe(false))
 const returnTo=router.currentRoute.value.fullPath
 host.querySelector<HTMLButtonElement>('.preview-all')!.click();await vi.waitFor(()=>expect(router.currentRoute.value.path).toBe('/preview'))
 const context=JSON.parse(String(router.currentRoute.value.query.list))
 expect(context).toMatchObject({source:'selected',workspace:'ei',returnTo,query:{collection:`${course}_selected`,bucket:'chosen',tier:'core',kind:'calculation',combined:'1',state:'review',type_group:'small'}})
 expect(router.currentRoute.value.query.question).toBe('selected-question')
})
