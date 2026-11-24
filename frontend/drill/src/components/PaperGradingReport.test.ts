// @vitest-environment jsdom
import { createApp, defineComponent, h, nextTick, type App } from 'vue'
import { describe, it, expect, vi, afterEach } from 'vitest'
import Report from './PaperGradingReport.vue'
import type { ExamPaper } from '../types'
const route = vi.hoisted(() => ({ query:{} as Record<string,string>, fullPath:'/papers/paper/review' }))
const replace = vi.hoisted(() => vi.fn())
vi.mock('vue-router', () => ({ useRoute:()=>route, useRouter:()=>({replace}) }))
vi.mock('./MarkdownSection.vue', () => ({ default: defineComponent({props:['title','source'],setup:p=>()=>h('section',p.title+' '+p.source)}) }))
const paper = {
 uuid:'paper', duration_minutes:180,
 items:[1,8].map(position => ({ position, question:{ uuid:`q${position}`, question_assets:[],answer_assets:[] } })),
 grading:{title:'批阅',exam_date:'2026-11-24',score:76.5,maximum:150,actual_duration_seconds:4200,summary:'非官方',strategy:'复习',conflicts:[],weaknesses:{电路原理:'参考方向'},subjects:[{subject:'电路原理',score:12.3,maximum:30}],items:[1,8].map(position => ({position,status:position===8?'incorrect':'correct',user_answer:'B',reference:'C',note:'译码器定义',priority:'P1',verification:'原图',earned:position===8?0:3,maximum:3}))}
} as unknown as ExamPaper

let app: App | undefined
let host: HTMLDivElement
async function setup() {
 route.query={};replace.mockClear()
 host=document.createElement('div');document.body.append(host)
 app=createApp(Report,{paper})
 app.component('RouterLink',defineComponent({props:['to'],setup:(p,{slots})=>()=>h('a',{href:p.to},slots.default?.())}))
 app.mount(host);await nextTick()
}
afterEach(()=>{app?.unmount();host?.remove()})
describe('paper grading report',()=>{
 it('shows unofficial weighted score and accessible subject charts',async()=>{
  await setup();expect(host.textContent).toContain('76.5');expect(host.textContent).toContain('非官方估分')
  expect(host.querySelectorAll('[role=meter]')).toHaveLength(2);expect(host.textContent).toContain('38.89%')
 })
 it('opens a per-question review and links to the real Practice route',async()=>{
  await setup();host.querySelectorAll<HTMLButtonElement>('.question-grid button')[1].click();await nextTick()
  expect(replace).toHaveBeenCalledWith({query:{question:'8'}})
  expect(host.querySelector('.review-toolbar a')?.getAttribute('href')).toContain('/practice/q8')
  expect(host.textContent).toContain('译码器定义')
 })
})
