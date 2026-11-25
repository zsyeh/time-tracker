// @vitest-environment jsdom
import {createApp,h,nextTick,type App} from 'vue'
import {it,expect,afterEach,vi} from 'vitest'
import Panel from './SprintProgressPanel.vue'
const prefs={values:{'timer.goal_plan':{mode:'sprint20',start_date:'2026-11-26'}},set:vi.fn(),flush:vi.fn().mockResolvedValue(undefined)}
vi.mock('../../shared/preferences/store',()=>({useAccountPreferences:()=>prefs}))
vi.mock('../../shared/ui/PreferenceSyncStatus.vue',()=>({default:{render:()=>null}}))
let app:App,host:HTMLDivElement
afterEach(()=>{app?.unmount();host?.remove()})
it('renders subject goals, uncapped actual percentages and bounded accessible bars',async()=>{
 const rows=[['math','数学二',300,400],['major','892专业课',240,200],['english','英语二',111,100],['training','政治',30,20]].map(([subject,label,target,base])=>({subject,label,target_minutes:target,base_minutes:base,actual_minutes:base,extra_minutes:0,remaining_minutes:Math.max(0,Number(target)-Number(base)),completion_percent:Math.round(Number(base)/Number(target)*1000)/10,task:'任务目标'}))
 const progress:any={name:'考研最后20天冲刺',start_date:'2026-11-26',end_date:'2026-12-15',day_index:1,today:{subjects:rows,credited_minutes:620,actual_minutes:720,extra_minutes:0,completion_percent:91,remaining_minutes:61},cumulative:{credited_minutes:620,actual_minutes:720,extra_minutes:0,completion_percent:4.6,completed_days:0}}
 host=document.createElement('div');document.body.append(host);app=createApp({render:()=>h(Panel,{progress,today:'2026-11-26'})});app.mount(host);await nextTick()
 expect(host.textContent).toContain('11小时21分');expect(host.textContent).toContain('133.3%');expect(host.textContent).toContain('227小时')
 const bars=[...host.querySelectorAll('[role=progressbar]')];expect(bars).toHaveLength(6)
 expect(bars.every(b=>Number(b.getAttribute('aria-valuenow'))<=100)).toBe(true)
 expect(host.querySelector('[data-subject=math] dd')?.textContent).toContain('5小时0分')
})
