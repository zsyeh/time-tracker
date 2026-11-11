// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import PracticeTrendPanel from './PracticeTrendPanel.vue'
import { api } from '../lib/api'
import { uiLanguage } from '../lib/uiPreferences'
const runtime=vi.hoisted(()=>({workspace:'drill'}))
vi.mock('../lib/runtimePath',()=>({get runtimeWorkspace(){return runtime.workspace}}))
const chartMocks=vi.hoisted(()=>({setOption:vi.fn(),resize:vi.fn(),dispose:vi.fn(),init:vi.fn()}))
vi.mock('echarts/core',()=>({use:vi.fn(),init:chartMocks.init}))
vi.mock('echarts/charts',()=>({BarChart:{},LineChart:{}}))
vi.mock('echarts/components',()=>({GridComponent:{},LegendComponent:{},TooltipComponent:{}}))
vi.mock('echarts/renderers',()=>({CanvasRenderer:{}}))
vi.mock('../lib/api',()=>({api:vi.fn()}))
let app:App|undefined,host:HTMLDivElement
const observers:Array<{observe:ReturnType<typeof vi.fn>;unobserve:ReturnType<typeof vi.fn>;disconnect:ReturnType<typeof vi.fn>}>=[]
const viewport=new EventTarget()
const payload=()=>({workspace:'drill',project_label:'Drill',today:'2026-11-11',range_days:30,daily_target:24,target_options:{minimum:18,standard:24,sprint:30},question_target:777,available_questions:900,
  goal:{total:777,covered:333,mastered:222,review:111,remaining:444,type_breakdown:{small:{total:440,covered:200,mastered:150,review:50,remaining:240},large:{total:337,covered:133,mastered:72,review:61,remaining:204},unknown:{total:0,covered:0,mastered:0,review:0,remaining:0}}},
  points:[{date:'2026-11-11',count:18,submissions:21,moving_average_7:22,target:24,is_today:true}],period:{daily_unique_total:90,submissions:110,different_questions:75},
  summary:{today:18,today_submissions:21,today_net_coverage:3,last7:140,average7:20,last14:270,average14:19.3,previous7:130,growth_percent:7.7,last30:500,streak:3,target_days_last7:4,completed_distinct:333,remaining:444},
  prediction:{deadline:'2026-11-21',original_deadline:'2026-11-22',days_remaining_including_today:11,remaining:444,required_daily:41,deadline_passed:false,notice:'',scenarios:[{label:'last7',window_days:7,available_history_days:7,history_sufficient:true,status:'ready',average:20,projected_added:217,projected_total:550,projected_toward_goal:550,shortfall:227,on_track:false,estimated_completion_date:'2026-12-03'}]}})
beforeEach(()=>{
  vi.clearAllMocks();localStorage.clear();uiLanguage.value='en';observers.length=0;runtime.workspace='drill'
  chartMocks.init.mockReturnValue(chartMocks)
  vi.stubGlobal('ResizeObserver',class{observe=vi.fn();unobserve=vi.fn();disconnect=vi.fn();constructor(){observers.push(this)}})
  vi.stubGlobal('visualViewport',viewport)
  vi.stubGlobal('requestAnimationFrame',(callback:FrameRequestCallback)=>window.setTimeout(()=>callback(0),0))
  vi.stubGlobal('cancelAnimationFrame',(id:number)=>window.clearTimeout(id))
  vi.stubGlobal('BroadcastChannel',class{onmessage=null;close=vi.fn()})
})
afterEach(()=>{app?.unmount();host?.remove();vi.restoreAllMocks();vi.unstubAllGlobals()})
async function settle(){await Promise.resolve();await nextTick();await nextTick();await new Promise(resolve=>setTimeout(resolve,5))}
async function mount(){host=document.createElement('div');document.body.append(host);app=createApp(PracticeTrendPanel);app.mount(host);await settle()}
it('shows dynamic goal, small/large remaining and distinct workload versus net new; secondary metrics start collapsed',async()=>{
  vi.mocked(api).mockResolvedValue(payload());await mount()
  expect(host.querySelectorAll('.primary-cards article')).toHaveLength(6)
  const primary=host.querySelector('.primary-cards')!.textContent!
  expect(primary).toContain('333');expect(primary).toContain('777');expect(primary).toContain('240');expect(primary).toContain('204')
  expect(primary).toContain('Today’s workload');expect(primary).toContain('Today’s net new coverage');expect(primary).toContain('+3')
  expect(host.textContent).toContain('2026-12-03');expect(host.textContent).toContain('227')
  expect(host.querySelector<HTMLDetailsElement>('.secondary-metrics')!.open).toBe(false)
  expect(vi.mocked(api).mock.calls[0]![0]).toContain('deadline=2026-11-21')
  expect(host.querySelector('.deadline-control')!.textContent).toContain('Original 11/22')
})
it('observes the asynchronously created chart and responds to orientation, viewport and page restoration with cleanup',async()=>{
  let resolve!:(value:unknown)=>void
  vi.mocked(api).mockImplementationOnce(()=>new Promise(finish=>{resolve=finish}))
  await mount();expect(observers[0]!.observe).not.toHaveBeenCalled()
  resolve(payload());await settle()
  expect(observers[0]!.observe).toHaveBeenCalledWith(host.querySelector('.trend-chart'))
  for(const event of ['orientationchange','pageshow','resize']){const before=chartMocks.resize.mock.calls.length;window.dispatchEvent(new Event(event));await settle();expect(chartMocks.resize.mock.calls.length).toBeGreaterThan(before)}
  const before=chartMocks.resize.mock.calls.length;viewport.dispatchEvent(new Event('resize'));await settle();expect(chartMocks.resize.mock.calls.length).toBeGreaterThan(before)
  app!.unmount();app=undefined
  expect(observers[0]!.disconnect).toHaveBeenCalledOnce();expect(chartMocks.dispose).toHaveBeenCalledOnce()
  const final=chartMocks.resize.mock.calls.length;window.dispatchEvent(new Event('orientationchange'));viewport.dispatchEvent(new Event('resize'));await settle();expect(chartMocks.resize).toHaveBeenCalledTimes(final)
})
it('keeps settings changes working when storage is full and switches labels with the language',async()=>{
  vi.mocked(api).mockResolvedValue(payload());await mount()
  vi.spyOn(Storage.prototype,'setItem').mockImplementation(()=>{throw new Error('quota')})
  const original=[...host.querySelectorAll<HTMLButtonElement>('.deadline-control button')].find(button=>button.textContent!.includes('11/22'))!
  original.click();await settle()
  expect(vi.mocked(api).mock.calls.at(-1)![0]).toContain('deadline=2026-11-22')
  uiLanguage.value='zh-CN';await nextTick()
  expect(host.textContent).toContain('按期完成所需每日净新增');expect(host.textContent).toContain('小题覆盖')
})
it('shows insufficient-history and overdue states without inventing a finish date or daily requirement',async()=>{
  const value=payload()
  Object.assign(value.prediction.scenarios[0]!,{status:'insufficient_history',history_sufficient:false,estimated_completion_date:null,shortfall:null,on_track:null,available_history_days:2})
  vi.mocked(api).mockResolvedValue(value);await mount()
  expect(host.textContent).toContain('Limited history');expect(host.textContent).toContain('Unknown')
  Object.assign(value.prediction,{deadline_passed:true,days_remaining_including_today:0,required_daily:null})
  vi.mocked(api).mockResolvedValue(structuredClone(value))
  window.dispatchEvent(new Event('focus'));await settle()
  expect(host.querySelector('.primary-cards')!.textContent).toContain('Deadline passed; choose a new date')
})

it('keeps the EI plan separate from actual full-bank coverage and does not assign plan deadlines to full-bank type counts',async()=>{
  runtime.workspace='ei'
  const value=payload()
  Object.assign(value,{workspace:'ei',project_label:'EI',question_target:307,available_questions:2798})
  Object.assign(value.goal,{total:307,covered:417,mastered:200,review:217,remaining:0})
  Object.assign(value.prediction,{remaining:0,required_daily:0})
  vi.mocked(api).mockResolvedValue(value);await mount()
  expect(host.querySelectorAll('.primary-cards article')).toHaveLength(4)
  const primary=host.querySelector('.primary-cards')!.textContent!
  expect(primary).toContain('Practiced / planned questions')
  expect(primary).toContain('417');expect(primary).toContain('307')
  expect(primary).toContain('Full-bank coverage 14.9%')
  expect(primary).toContain('Mastery 7.1%')
  expect(primary).not.toContain('135.8%')
  expect(primary).not.toContain('Small questions')
  expect(host.textContent).toContain('Planned question target reached')
})
it.each([
  ['practice.trend.settings.v1.drill','2026-11-22','2026-11-21'],
  ['practice.trend.settings.v1.drill','2026-11-20','2026-11-20'],
  ['practice.trend.settings.v2.drill','2026-11-22','2026-11-22'],
])('migrates legacy default dates while preserving custom/current settings (%s %s)',async(key,saved,expected)=>{
  localStorage.setItem(key,JSON.stringify({target:42,deadline:saved}))
  vi.mocked(api).mockResolvedValue(payload());await mount()
  expect(vi.mocked(api).mock.calls[0]![0]).toContain(`deadline=${expected}`)
  expect(vi.mocked(api).mock.calls[0]![0]).toContain('target=42')
})
it('renders selected coverage and independent small/large daily requirements from the server goal',async()=>{
  const value=payload()
  Object.assign(value.goal,{total:963,covered:502,mastered:342,review:160,remaining:461})
  Object.assign(value.goal.type_breakdown.small,{total:619,covered:345,mastered:259,review:86,remaining:274,required_daily:25})
  Object.assign(value.goal.type_breakdown.large,{total:344,covered:157,mastered:83,review:74,remaining:187,required_daily:17})
  Object.assign(value.prediction,{remaining:461,required_daily:42})
  vi.mocked(api).mockResolvedValue(value);await mount()
  const cards=host.querySelectorAll('.primary-cards article')
  expect(cards[0]!.textContent).toContain('502/ 963');expect(cards[0]!.textContent).toContain('Coverage 52.1%');expect(cards[0]!.textContent).toContain('Mastery 35.5%')
  expect(cards[1]!.textContent).toContain('461')
  expect(cards[2]!.textContent).toContain('Remaining 274 · Net new / day needed 25')
  expect(cards[3]!.textContent).toContain('Remaining 187 · Net new / day needed 17')
  expect(cards[5]!.textContent).toContain('42')
})
it('does not call an empty selected scope a completed goal',async()=>{
  const value=payload()
  Object.assign(value.goal,{status:'empty_scope',total:0,covered:0,mastered:0,review:0,remaining:0})
  Object.assign(value.prediction,{remaining:0,required_daily:null,remaining_determinable:false})
  Object.assign(value.prediction.scenarios[0]!,{status:'empty_scope',shortfall:null,on_track:null,estimated_completion_date:null})
  vi.mocked(api).mockResolvedValue(value);await mount()
  expect(host.textContent).toContain('No questions in this scope; check the selected scope')
  expect(host.textContent).not.toContain('Coverage goal reached')
  expect(host.querySelector('.prediction-panel header .on-track')).toBeNull()
})
