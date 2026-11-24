// @vitest-environment jsdom
import { createApp, defineComponent, h, nextTick, type App } from 'vue'
import { afterEach, expect, it, vi } from 'vitest'
import Table from './GradingReviewTable.vue'
import type { ExamGrading } from '../types'
import { api } from '../lib/api'
vi.mock('../lib/api',()=>({api:vi.fn()}))
vi.mock('./MarkdownAnswer.vue',()=>({default:defineComponent({props:['source'],setup:p=>()=>h('div',p.source)})}))
let app:App|undefined,host:HTMLDivElement
const review={position:8,question_uuid:'q8',status:'incorrect',user_answer:'B',reference:'C',note:'译码器',priority:'P1',verification:'原图',earned:0,maximum:3}
async function settle(){for(let i=0;i<5;i++){await Promise.resolve();await nextTick()}}
async function setup(){host=document.createElement('div');document.body.append(host);app=createApp(Table,{paperUuid:'paper',review:{...review} as ExamGrading['items'][number]});app.mount(host);await settle()}
function button(text:string){return [...host.querySelectorAll('button')].find(b=>b.textContent===text)!}
afterEach(()=>{app?.unmount();host?.remove();vi.clearAllMocks()})
it('renders five readable table rows and the earned/maximum score below',async()=>{await setup();expect(host.querySelectorAll('tbody tr')).toHaveLength(5);expect(host.querySelector('.question-score strong')?.textContent).toBe('0/3')})
it('saves only edited fields with expected original values',async()=>{
 await setup();vi.mocked(api).mockResolvedValue({item:{...review,reference:'C（核实）'}})
 button('编辑批阅').click();await settle();const field=host.querySelector<HTMLTextAreaElement>('#review-8-reference')!;field.value='C（核实）';field.dispatchEvent(new Event('input'));await settle()
 button('保存修改').click();await settle()
 expect(api).toHaveBeenCalledWith('/api/drill/papers/paper/items/8/grading/',expect.objectContaining({method:'PATCH',body:JSON.stringify({expected_question_uuid:'q8',changes:{reference:'C（核实）'},expected:{reference:'C'}})}))
 expect(host.textContent).toContain('已保存')
})
it('keeps draft and shows a recoverable save error',async()=>{
 await setup();vi.mocked(api).mockRejectedValue(new Error('其他页面已修改'))
 button('编辑批阅').click();await settle();const field=host.querySelector<HTMLTextAreaElement>('#review-8-note')!;field.value='修订';field.dispatchEvent(new Event('input'));await settle();button('保存修改').click();await settle()
 expect(host.querySelector('[role=alert]')?.textContent).toContain('其他页面已修改');expect(field.value).toBe('修订')
})
