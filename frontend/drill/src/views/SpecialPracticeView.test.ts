// @vitest-environment jsdom
import { afterEach,expect,it,vi } from 'vitest'
import { createApp,defineComponent,h,nextTick,type App } from 'vue'
import View from './SpecialPracticeView.vue'
import { api } from '../lib/api'
vi.mock('../lib/api',()=>({api:vi.fn()}))
let app:App|undefined,host:HTMLDivElement
async function mount(){host=document.createElement('div');document.body.append(host);app=createApp(View);app.component('RouterLink',defineComponent({props:['to'],setup:(p,{slots})=>()=>h('a',{'data-to':JSON.stringify(p.to)},slots.default?.())}));app.mount(host);for(let i=0;i<6;i++){await Promise.resolve();await nextTick()}}
afterEach(()=>{app?.unmount();host?.remove();vi.clearAllMocks()})
it('opens an Agent collection in standard Practice with its fixed order and return context',async()=>{
 vi.mocked(api).mockResolvedValue({results:[{uuid:'p1',title:'偏导专项',description:'针对薄弱点',question_count:25,first_question:'q2',first_item:7,created_at:'2026-11-25T00:00:00Z'}]})
 await mount();expect(host.textContent).toContain('偏导专项')
 const start=JSON.parse(host.querySelector('a')!.getAttribute('data-to')!)
 expect(start.path).toBe('/practice/q2');expect(start.query.entry).toBe('paper:7')
 expect(JSON.parse(start.query.list)).toMatchObject({source:'paper',query:{paper:'p1'},returnTo:'/special-practice'})
})
it('explains the Agent push workflow when the private list is empty',async()=>{vi.mocked(api).mockResolvedValue({results:[]});await mount();expect(host.textContent).toContain('暂无专练题单')})
