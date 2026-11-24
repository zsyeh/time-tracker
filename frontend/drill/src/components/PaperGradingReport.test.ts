// @vitest-environment jsdom
import { createApp, defineComponent, h, nextTick, onMounted, type App } from 'vue'
import { describe, it, expect, vi, afterEach } from 'vitest'
import Report from './PaperGradingReport.vue'
import type { ExamPaper } from '../types'
const route = vi.hoisted(() => ({ query:{} as Record<string,string>, fullPath:'/papers/paper/review' }))
const replace = vi.hoisted(() => vi.fn())
vi.mock('../lib/api',()=>({api:vi.fn()}))
vi.mock('./MarkdownAnswer.vue',()=>({default:defineComponent({props:['source'],setup:p=>()=>h('div',p.source)})}))
vi.mock('vue-router', () => ({ useRoute:()=>route, useRouter:()=>({replace}), onBeforeRouteLeave:vi.fn(), onBeforeRouteUpdate:vi.fn() }))
vi.mock('./MarkdownSection.vue', () => ({ default: defineComponent({props:['title','source'],emits:['rendered'],setup:(p,{emit})=>{onMounted(()=>emit('rendered'));return ()=>h('section',p.title+' '+p.source)}}) }))
const paper = {
 uuid:'paper', duration_minutes:180,
 items:[1,8].map(position => ({ position, question:{ uuid:`q${position}`, question_assets:[],answer_assets:[] } })),
 grading:{title:'批阅',exam_date:'2026-11-24',score:76.5,maximum:150,actual_duration_seconds:4200,summary:'非官方',strategy:'复习',conflicts:[],weaknesses:{电路原理:'参考方向'},subjects:[{subject:'电路原理',score:12.3,maximum:30}],items:[1,8].map(position => ({position,status:position===8?'incorrect':'correct',user_answer:'B',reference:'C',note:'译码器定义',priority:'P1',verification:'原图',earned:position===8?0:3,maximum:3}))}
} as unknown as ExamPaper

let app: App | undefined
let host: HTMLDivElement
async function setup(question?: string) {
 route.query=question ? { question } : {};replace.mockClear()
 HTMLElement.prototype.scrollIntoView = vi.fn()
 host=document.createElement('div');document.body.append(host)
 app=createApp(Report,{paper})
 app.component('RouterLink',defineComponent({props:['to'],setup:(p,{slots})=>()=>h('a',{href:p.to},slots.default?.())}))
 app.mount(host);await nextTick()
}
afterEach(()=>{app?.unmount();host?.remove()})
describe('paper grading report',()=>{
 it('reveals a deep-linked question after its asynchronously mounted detail exists',async()=>{
  await setup('8');await nextTick()
  expect(HTMLElement.prototype.scrollIntoView).toHaveBeenCalledWith({block:'start',behavior:'auto'})
  expect(host.querySelector('.review-toolbar')?.textContent).toContain('第 8')
 })
 it('shows unofficial weighted score and accessible subject charts',async()=>{
  await setup();expect(host.textContent).toContain('76.5');expect(host.textContent).toContain('非官方估分')
  expect(host.querySelectorAll('[role=meter]')).toHaveLength(2);expect(host.textContent).toContain('38.89%')
 })
 it('opens a per-question review and links to the real Practice route',async()=>{
  await setup();host.querySelectorAll<HTMLButtonElement>('.question-grid button')[1].click();await nextTick()
  expect(replace).toHaveBeenCalledWith({query:{question:'8'}})
  expect(host.querySelector('.review-toolbar a')?.getAttribute('href')).toContain('/practice/q8')
  expect(host.querySelector('#paper-review-detail')).not.toBeNull()
  expect(host.querySelector('.report-links a:last-child')?.getAttribute('href')).toBe('/papers/paper/review?mode=all')
  expect(host.textContent).toContain('译码器定义')
  expect(host.querySelector('.review-original-question')?.hasAttribute('open')).toBe(true)
  expect(host.querySelector('.review-original-answer')?.hasAttribute('open')).toBe(true)
 })
})
