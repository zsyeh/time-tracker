<script setup lang="ts">
import { typeText } from '../lib/examTypes'
import { uiText } from '../lib/uiText'
import { uiLanguage } from '../lib/uiPreferences'
import { useAccountPreferences } from '../../../shared/preferences/store'
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { ECharts, EChartsCoreOption } from 'echarts/core'
import { api } from '../lib/api'
import { practiceTrendChannel, practiceTrendEvent, practiceTrendStoragePulse } from '../lib/practiceTrend'
import { runtimeWorkspace } from '../lib/runtimePath'
import { chartPalette, chartVisuals, onChartAppearanceChanged } from '../lib/chartTheme'

echarts.use([BarChart, LineChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer])

type Scenario = { label:string; average:number|null; projected_added:number|null; projected_total:number|null; projected_toward_goal:number|null; shortfall:number|null; on_track:boolean|null; window_days?:number; available_history_days?:number; history_sufficient?:boolean; status?:'ready'|'insufficient_history'|'no_positive_rate'|'past_deadline'|'complete'|'empty_scope'; estimated_completion_date?:string|null }
type Coverage = {total:number;covered:number;mastered:number;review:number;remaining:number;required_daily?:number|null}
type Goal = Coverage & {metric:string;status?:'active'|'empty_scope';type_breakdown:{small:Coverage;large:Coverage;unknown:Coverage}}
type TrendPayload = {
  workspace:'drill'|'ei'; project_label:string; timezone:string; today:string; range_days:number; allowed_ranges:number[]
  daily_target:number; target_options:{minimum:number;standard:number;sprint:number}; question_target:number; available_questions:number
  points:Array<{date:string;count:number;submissions:number;moving_average_7:number;target:number;is_today:boolean;is_complete_day:boolean}>
  period:{submissions:number;different_questions:number;daily_unique_total:number}
  goal?:Goal
  summary:{today_net_coverage?:number;today_new_coverage?:number;today_removed_coverage?:number;today:number;today_submissions:number;last7:number;average7:number;last14:number;average14:number;previous7:number;growth_percent:number|null;last30:number;streak:number;target_days_last7:number;completed_distinct:number;remaining:number}
  comparison_windows:{last7:{start:string;end:string};previous7:{start:string;end:string};excludes_today:boolean}
  prediction:{original_deadline?:string;forecast_basis?:string;deadline_passed?:boolean;deadline:string;days_remaining_including_today:number;remaining_determinable:boolean;remaining:number;required_daily:number|null;scenarios:Scenario[];notice:string}
}

const isEi = runtimeWorkspace === 'ei'
const workspaceHint = isEi ? 'ei' : 'drill'
const preferences = useAccountPreferences()
const progressKey = `progress.${workspaceHint}` as const
const displayedTypes:Array<'small'|'large'>=isEi?[]:['small','large']
const rangeDays = ref(30), dailyTarget = ref(isEi ? 11 : 24), deadline = ref('2026-11-21')
const customTarget = ref(dailyTarget.value), data = ref<TrendPayload|null>(null)
const loading = ref(true), refreshing = ref(false), error = ref(''), chartElement = ref<HTMLElement|null>(null)
let chart:ECharts|null=null, resizeObserver:ResizeObserver|null=null, schemeObserver:MutationObserver|null=null, channel:BroadcastChannel|null=null
let refreshTimer=0, loadSequence=0, resizeFrame=0
let observedElement:HTMLElement|null=null
let mounted=false
let stopAppearance:(()=>void)|undefined

const growthText=computed(()=>{const value=data.value?.summary.growth_percent;return value===null||value===undefined?uiText("无可比基线"):`${value>0?'+':''}${value}%`})
const growthClass=computed(()=>{const value=data.value?.summary.growth_percent;return value===null||value===undefined?'':value>0?'positive':value<0?'negative':''})
const targetProgress=computed(()=>data.value?Math.min(100,Math.round(data.value.summary.today*100/Math.max(1,data.value.daily_target))):0)
const todayRemaining=computed(()=>data.value?Math.max(0,data.value.daily_target-data.value.summary.today):0)

const goal=computed(()=>data.value?.goal)
const coverageDenominator=computed(()=>isEi?data.value?.available_questions:goal.value?.total)
const coveragePercent=computed(()=>goal.value&&coverageDenominator.value?Math.round(goal.value.covered*1000/coverageDenominator.value)/10:0)
const masteryPercent=computed(()=>goal.value&&coverageDenominator.value?Math.round(goal.value.mastered*1000/coverageDenominator.value)/10:0)
const pastDeadline=computed(()=>Boolean(data.value&&(data.value.prediction.deadline_passed||data.value.prediction.days_remaining_including_today<=0)))
const primaryScenario=computed(()=>data.value?.prediction.scenarios[0])
const emptyScope=computed(()=>goal.value?.status==='empty_scope'||goal.value?.total===0)
const dailyNeed=computed(()=>pastDeadline.value||emptyScope.value?null:data.value?.prediction.required_daily??null)
function typeNeed(kind:'small'|'large'){
  const group=goal.value?.type_breakdown[kind],days=data.value?.prediction.days_remaining_including_today||0
  if(!group||days<=0||emptyScope.value)return null
  return group.required_daily!==undefined?group.required_daily:Math.ceil(group.remaining/days)
}
function signed(value:number|undefined){return value===undefined?typeText('未知','Unknown'):`${value>0?'+':''}${value}`}
function scenarioTitle(scenario:Scenario){
  if(scenario.window_days===7)return typeText('近7完整日净新增','Net new · last 7 full days')
  if(scenario.window_days===14)return typeText('近14完整日净新增','Net new · last 14 full days')
  return uiText(scenario.label)
}
function scenarioStatus(scenario:Scenario){
  if(scenario.status==='empty_scope')return typeText('所选范围暂无题目，无法预测','No questions in this scope; forecast unavailable')
  if(scenario.status==='complete')return isEi?typeText('已完成计划题量','Planned question target reached'):typeText('已完成覆盖目标','Coverage goal reached')
  if(scenario.status==='past_deadline')return typeText('目标日期已过','Deadline passed')
  if(scenario.status==='insufficient_history'||scenario.history_sufficient===false)return typeText('历史不足，预测仅供参考','Limited history; forecast is provisional')
  if(scenario.status==='no_positive_rate')return typeText('暂无正向净新增速度，无法推算日期','No positive net rate; completion date unknown')
  return scenario.on_track?typeText('预计可按期完成','On track to finish'):typeText('当前速度不足以按期完成','Not on track at this pace')
}

function loadSettings(){
  // Only the authenticated account store supplies persistent goals. Legacy
  // browser keys are imported explicitly from Settings, never across accounts.
  const saved=preferences.values[progressKey]
  dailyTarget.value=saved.target
  deadline.value=saved.deadline
  customTarget.value=saved.target
}

function persistSettings(){preferences.set(progressKey,{target:dailyTarget.value,deadline:deadline.value})}

function chartOption():EChartsCoreOption{
  const payload=data.value!,palette=chartPalette(),{text,border,surface,primary,accent}=palette,average=palette.comparison,todayColor=palette.accent
  return {...chartVisuals(palette),grid:{left:42,right:16,top:44,bottom:34},legend:{top:3,left:0,itemWidth:13,itemHeight:7,textStyle:{color:text,fontSize:12},data:[uiText("每日题量"),uiText("7天移动平均"),uiText("目标线")]},tooltip:{trigger:'axis',confine:true,backgroundColor:surface,borderColor:border,textStyle:{color:primary,fontSize:14},formatter(params:unknown){const list=params as Array<{axisValue:string;seriesName:string;value:number;marker:string;dataIndex:number}>,index=list[0]?.dataIndex??0,point=payload.points[index];if(!point)return'';return [`<strong>${point.date}${point.is_today?uiText(" · 今天（进行中）"):''}</strong>`,...list.map(item=>`${item.marker}${item.seriesName}：${item.value}`),`${uiText("提交次数")}：${point.submissions}`].join('<br>')}},xAxis:{type:'category',data:payload.points.map(point=>point.date.slice(5)),axisLine:{lineStyle:{color:border}},axisTick:{show:false},axisLabel:{color:(_value:string,index:number)=>payload.points[index]?.is_today?todayColor:text,fontSize:12,hideOverlap:true}},yAxis:{type:'value',min:0,minInterval:1,axisLabel:{color:text,fontSize:12},axisLine:{show:false},axisTick:{show:false},splitLine:{lineStyle:{color:border,type:'dashed',opacity:.75}}},series:[{name:uiText("每日题量"),type:'bar',barMaxWidth:22,data:payload.points.map(point=>({value:point.count,itemStyle:{color:point.is_today?todayColor:accent,borderRadius:[3,3,0,0],opacity:point.is_today?1:.82}}))},{name:uiText("7天移动平均"),type:'line',smooth:.28,symbol:'circle',symbolSize:4,data:payload.points.map(point=>point.moving_average_7),lineStyle:{color:average,width:2},itemStyle:{color:average}},{name:uiText("目标线"),type:'line',symbol:'none',silent:true,data:payload.points.map(()=>payload.daily_target),lineStyle:{color:todayColor,width:1.5,type:'dashed'}}]}
}

function resizeChart(){
  if(resizeFrame)window.cancelAnimationFrame(resizeFrame)
  resizeFrame=window.requestAnimationFrame(()=>{resizeFrame=0;if(mounted)chart?.resize()})
}
function observeChartElement(){
  const element=chartElement.value
  if(observedElement===element)return
  if(observedElement)resizeObserver?.unobserve(observedElement)
  chart?.dispose();chart=null
  observedElement=element
  if(element)resizeObserver?.observe(element)
}
async function renderChart(){
  if(!data.value)return
  await nextTick()
  if(!mounted||!chartElement.value)return
  observeChartElement()
  chart||=echarts.init(chartElement.value)
  chart.setOption(chartOption(),true)
  resizeChart()
}
async function load(silent=false){const sequence=++loadSequence;if(silent)refreshing.value=true;else loading.value=true;error.value='';try{const params=new URLSearchParams({days:String(rangeDays.value),target:String(dailyTarget.value),deadline:deadline.value}),payload=await api<TrendPayload>(`/api/drill/practice-trends/?${params}`);if(sequence!==loadSequence)return;data.value=payload;dailyTarget.value=payload.daily_target;customTarget.value=payload.daily_target;await renderChart()}catch(reason){if(sequence===loadSequence)error.value=(reason as Error).message}finally{if(sequence===loadSequence){loading.value=false;refreshing.value=false}}}
function setRange(value:number){if(rangeDays.value===value)return;rangeDays.value=value;void load()}
function setTarget(value:number){dailyTarget.value=value;customTarget.value=value;persistSettings();void load(true)}
function applyCustomTarget(){setTarget(Math.max(1,Math.min(500,Math.round(Number(customTarget.value)||dailyTarget.value))))}
function changeDeadline(){
  const date=new Date(`${deadline.value}T00:00:00Z`)
  if(!/^\d{4}-\d{2}-\d{2}$/.test(deadline.value)||!Number.isFinite(date.getTime())||date.toISOString().slice(0,10)!==deadline.value){loadSettings();return}
  persistSettings();void load(true)
}
function externalRefresh(){void load(true)}
function storageChanged(event:StorageEvent){if(event.key===practiceTrendStoragePulse)externalRefresh()}
function visibilityChanged(){if(document.visibilityState==='visible'){resizeChart();externalRefresh()}}

onMounted(()=>{
  mounted=true
  if(typeof ResizeObserver!=='undefined')resizeObserver=new ResizeObserver(resizeChart)
  loadSettings();void load()
  schemeObserver=new MutationObserver(()=>void renderChart())
  schemeObserver.observe(document.documentElement,{attributes:true,attributeFilter:['data-color-scheme','data-accent']})
  stopAppearance=onChartAppearanceChanged(()=>void renderChart())
  window.addEventListener(practiceTrendEvent,externalRefresh)
  window.addEventListener('storage',storageChanged)
  window.addEventListener('focus',externalRefresh)
  window.addEventListener('resize',resizeChart)
  window.addEventListener('orientationchange',resizeChart)
  window.addEventListener('pageshow',resizeChart)
  window.visualViewport?.addEventListener('resize',resizeChart)
  document.addEventListener('visibilitychange',visibilityChanged)
  if('BroadcastChannel'in window){channel=new BroadcastChannel(practiceTrendChannel);channel.onmessage=externalRefresh}
  refreshTimer=window.setInterval(()=>{if(document.visibilityState==='visible')externalRefresh()},120_000)
})
onUnmounted(()=>{
  mounted=false;loadSequence+=1
  window.clearInterval(refreshTimer);window.cancelAnimationFrame(resizeFrame)
  resizeObserver?.disconnect();schemeObserver?.disconnect();channel?.close();chart?.dispose()
  stopAppearance?.()
  window.removeEventListener(practiceTrendEvent,externalRefresh)
  window.removeEventListener('storage',storageChanged)
  window.removeEventListener('focus',externalRefresh)
  window.removeEventListener('resize',resizeChart)
  window.removeEventListener('orientationchange',resizeChart)
  window.removeEventListener('pageshow',resizeChart)
  window.visualViewport?.removeEventListener('resize',resizeChart)
  document.removeEventListener('visibilitychange',visibilityChanged)
})
watch(chartElement,()=>{observeChartElement();void renderChart()},{flush:'post'})

// Primitive sources ignore unrelated preferences and same-value server ack
// clones. A local action updates refs before store.set, so it fetches only once.
watch([()=>preferences.values[progressKey].target,()=>preferences.values[progressKey].deadline],()=>{
  const saved=preferences.values[progressKey]
  if(saved.target===dailyTarget.value&&saved.deadline===deadline.value)return
  loadSettings()
  if(mounted)void load(true)
})

watch(uiLanguage, () => { void renderChart() })
</script>

<template>
  <section class="practice-trend" aria-labelledby="practice-trend-title" aria-describedby="practice-trend-description">
    <header class="trend-header">
      <div><p id="practice-trend-description">{{ typeText('覆盖按当前最新状态；每日题量包含重做，不等于净新增。','Coverage uses current latest states. Daily workload includes repeats and differs from net new coverage.') }}</p></div>
    </header>
    <p v-if="error" class="trend-error" role="alert">{{ uiText(error) }} <button @click="load()">{{ uiText("重试") }}</button></p><div v-if="loading&&!data" class="trend-loading">{{ uiText("正在计算历史趋势…") }}</div>
    <template v-else-if="data">
      <div class="trend-cards primary-cards" :class="{'ei-plan':isEi}">
        <h2 id="practice-trend-title" class="trend-group-heading">{{ typeText('目标概览', 'Goal overview') }}</h2>
        <article><small>{{ isEi?typeText('已做 / 计划题量','Practiced / planned questions'):typeText('严选覆盖 / 总题量','Selected covered / total') }}</small><strong>{{ goal?.covered ?? data.summary.completed_distinct }}<em>/ {{ goal?.total ?? data.question_target }}</em></strong><span v-if="goal">{{ isEi?typeText('全题库覆盖率','Full-bank coverage'):typeText('覆盖率','Coverage') }} {{ coveragePercent }}% · {{ typeText('掌握率','Mastery') }} {{ masteryPercent }}%</span><span v-if="goal">{{ typeText('掌握','Mastered') }} {{ goal.mastered }} · {{ typeText('待复习','Review') }} {{ goal.review }}</span><span v-else>{{ uiText('按每题最新状态') }}</span><span>{{ typeText('截止日', 'Deadline') }} {{ data.prediction.deadline }} · {{ data.prediction.remaining === 0 ? typeText('已完成', 'Complete') : typeText('进行中', 'In progress') }}</span></article>
        <article><small>{{ isEi?typeText('计划剩余','Remaining to plan'):typeText('尚未覆盖','Not covered yet') }}</small><strong>{{ goal?.remaining ?? data.summary.remaining }}<em>{{ uiText('道') }}</em></strong><span>{{ isEi?typeText('原计划独立保留，不代表已覆盖全部题库','Original plan retained; reaching it does not mean full-bank coverage'):typeText('已做 = 掌握 + 待复习；覆盖不等于掌握','Covered = mastered + review; coverage differs from mastery') }}</span></article>
        <h3 v-if="!isEi" class="trend-group-heading">{{ typeText('分项进度', 'Progress by type') }}</h3>
        <article v-for="kind in displayedTypes" :key="kind"><small>{{ kind==='small'?typeText('小题覆盖 / 总数','Small questions · covered / total'):typeText('大题覆盖 / 总数','Large questions · covered / total') }}</small><strong>{{ goal?.type_breakdown[kind]?.covered ?? '—' }}<em>/ {{ goal?.type_breakdown[kind]?.total ?? '—' }}</em></strong><span>{{ typeText('剩余','Remaining') }} {{ goal?.type_breakdown[kind]?.remaining ?? '—' }} · {{ typeText('每日需新增','Net new / day needed') }} {{ typeNeed(kind) ?? '—' }}</span><span v-if="goal">{{ typeText('掌握','Mastered') }} {{ goal.type_breakdown[kind].mastered }} · {{ typeText('待复习','Review') }} {{ goal.type_breakdown[kind].review }}</span></article>
        <h3 class="trend-group-heading">{{ typeText('今日任务', 'Today’s task') }}</h3>
        <article><small>{{ typeText('全题库今日工作量 / 每日目标','Today’s workload / daily target (all questions)') }}</small><strong>{{ data.summary.today }}<em>/ {{ data.daily_target }}</em></strong><i><b :style="{width:`${targetProgress}%`}" /></i><span>{{ typeText('今日剩余工作量','Workload remaining today') }} {{ todayRemaining }} · {{ typeText('今日净新增覆盖','Today’s net new coverage') }} {{ signed(data.summary.today_net_coverage) }}</span></article>
        <article><small>{{ typeText('按期完成所需每日净新增','Net new per day needed') }}</small><strong>{{ dailyNeed ?? '—' }}<em v-if="dailyNeed!==null">{{ uiText('道') }}</em></strong><span v-if="pastDeadline" class="behind">{{ typeText('已逾期，请调整目标日期','Deadline passed; choose a new date') }}</span><span v-else>{{ data.prediction.deadline }} · {{ typeText('含今天还剩','Days left including today:') }} {{ data.prediction.days_remaining_including_today }}</span></article>
      </div>
      <div class="trend-controls">
        <div><span>{{ uiText("每日目标") }}</span><button :class="{active:dailyTarget===data.target_options.minimum}" @click="setTarget(data.target_options.minimum)">{{ uiText("保底") }} {{ data.target_options.minimum }}</button><button :class="{active:dailyTarget===data.target_options.standard}" @click="setTarget(data.target_options.standard)">{{ uiText("标准") }} {{ data.target_options.standard }}</button><button :class="{active:dailyTarget===data.target_options.sprint}" @click="setTarget(data.target_options.sprint)">{{ uiText("冲刺") }} {{ data.target_options.sprint }}</button><label>{{ uiText("自定") }} <input v-model.number="customTarget" type="number" min="1" max="500" @change="applyCustomTarget"></label></div>
        <div class="deadline-control"><span>{{ typeText('争取完成日 · 北京时间23:59','Target date · 23:59 Beijing time') }}</span><button :class="{active:deadline==='2026-11-21'}" @click="deadline='2026-11-21';changeDeadline()">11/21</button><button :class="{active:deadline==='2026-11-22'}" @click="deadline='2026-11-22';changeDeadline()">{{ typeText('原定','Original') }} 11/22</button><input v-model="deadline" :aria-label="uiText('目标截止日')" type="date" @change="changeDeadline"></div><span v-if="refreshing" class="refreshing">{{ uiText("同步中…") }}</span>
      </div>
      <section class="prediction-panel">
        <header><div><h3>{{ typeText('能否按期完成？','Will I finish on time?') }}</h3></div><strong v-if="emptyScope">{{ typeText('所选范围暂无题目，请检查筛选范围','No questions in this scope; check the selected scope') }}</strong><strong v-else-if="data.prediction.remaining===0" class="on-track">{{ isEi?typeText('计划题量目标已完成','Planned question target reached'):typeText('覆盖目标已完成','Coverage goal reached') }}</strong><strong v-else-if="pastDeadline" class="behind">{{ typeText('目标日期已过','Deadline passed') }}</strong><strong v-else-if="primaryScenario" :class="primaryScenario.on_track===true?'on-track':primaryScenario.on_track===false?'behind':''">{{ scenarioStatus(primaryScenario) }}</strong></header>
        <div v-if="primaryScenario&&data.prediction.remaining>0" class="forecast-answer"><span>{{ typeText('预计完成日期','Estimated completion') }} <b>{{ primaryScenario.estimated_completion_date ?? typeText('暂无法确定','Unknown') }}</b></span><span>{{ typeText('截止日预计还差','Expected shortfall by deadline') }} <b>{{ primaryScenario.shortfall ?? '—' }} {{ uiText('道') }}</b></span></div>
        <div class="prediction-grid"><article v-for="scenario in data.prediction.scenarios" :key="scenario.label"><small>{{ scenarioTitle(scenario) }}</small><strong>{{ scenario.average ?? '—' }}<em>{{ typeText('净新增 / 日','net new / day') }}</em></strong><span>{{ scenarioStatus(scenario) }}</span><span>{{ typeText('完成日期','Finish date') }} {{ scenario.estimated_completion_date ?? '—' }} · {{ typeText('还差','Shortfall') }} {{ scenario.shortfall ?? '—' }}</span><small v-if="scenario.available_history_days!==undefined&&scenario.window_days">{{ typeText('可用历史','Available history') }} {{ scenario.available_history_days }}/{{ scenario.window_days }} {{ uiText('天') }}</small></article></div>
        <p>{{ data.prediction.notice==='按现有速度估算，不构成完成承诺。'?typeText('按现有速度估算，不构成完成承诺。','Estimates use recent pace and do not guarantee completion.'):uiText(data.prediction.notice) }} {{ typeText('历史速度排除今天；今日工作量不等同净新增。预测不是完成保证。','Historical rates exclude today. Workload differs from net new coverage; forecasts are not guarantees.') }}</p>
      </section>
      <div class="trend-chart-heading"><h3>{{ typeText('每日刷题趋势', 'Daily practice trend') }}</h3><div class="range-switch" :aria-label="uiText('趋势日期范围')"><button v-for="days in [7,14,30,50,90]" :key="days" :class="{active:rangeDays===days}" @click="setRange(days)">{{ days }}{{ uiText("天") }}</button></div></div>
      <div ref="chartElement" class="trend-chart" role="img" :aria-label="typeText(`${data.range_days}天每日刷题量、7天移动平均和每日目标趋势图`,`${data.range_days}-day daily workload, 7-day moving average and daily target chart`)" />
      <details class="chart-data"><summary>{{ typeText('查看趋势数据', 'View trend data') }}</summary><div class="chart-table-scroll"><table><caption>{{ typeText('每日工作量与移动平均', 'Daily workload and moving average') }}</caption><thead><tr><th scope="col">{{ uiText('日期') }}</th><th scope="col">{{ uiText('每日题量') }}</th><th scope="col">{{ uiText('提交次数') }}</th><th scope="col">{{ uiText('7天移动平均') }}</th></tr></thead><tbody><tr v-for="point in data.points" :key="point.date"><th scope="row">{{ point.date }}</th><td>{{ point.count }}</td><td>{{ point.submissions }}</td><td>{{ point.moving_average_7 }}</td></tr></tbody></table></div></details>
      <p v-if="!data.points.length" class="chart-footnote">{{ typeText('当前范围暂无趋势数据。', 'No trend data in this range.') }}</p>
      <footer class="chart-footnote"><span>{{ uiText("周期内按日累计") }} {{ data.period.daily_unique_total }} {{ uiText("道") }}</span><span>{{ data.period.submissions }} {{ uiText("次有效提交") }}</span><span>{{ data.period.different_questions }} {{ uiText("道不同题目") }}</span></footer>
      <details class="secondary-metrics"><summary>{{ typeText('更多统计 · 历史工作量与活跃情况','More statistics · historical workload and activity') }}</summary><div class="trend-cards"><article><small>{{ uiText("最近7个完整日") }}</small><strong>{{ data.summary.last7 }}</strong><span>{{ uiText("日均") }} {{ data.summary.average7 }}</span></article><article><small>{{ typeText('最近14个完整日','Last 14 complete days') }}</small><strong>{{ data.summary.last14 }}</strong><span>{{ uiText('日均') }} {{ data.summary.average14 }}</span></article><article><small>{{ uiText("相比前7个完整日") }}</small><strong :class="growthClass">{{ growthText }}</strong><span>{{ data.summary.previous7 }} → {{ data.summary.last7 }}</span></article><article><small>{{ uiText("最近30天") }}</small><strong>{{ data.summary.last30 }}</strong><span>{{ uiText("含今天") }}</span></article><article><small>{{ uiText("连续活跃") }}</small><strong>{{ data.summary.streak }}<em>{{ uiText('天') }}</em></strong><span>{{ uiText("近7日达标") }} {{ data.summary.target_days_last7 }}</span></article><article><small>{{ typeText('今日提交次数','Today’s submissions') }}</small><strong>{{ data.summary.today_submissions }}</strong><span>{{ typeText('包含重做；不等于覆盖新增','Includes repeats; differs from new coverage') }}</span></article></div></details>
    </template>
  </section>
</template>

<style scoped>
.practice-trend { container-type:inline-size; box-sizing:border-box; min-width:0; max-width:100%; margin:0 0 24px; padding:0; }
.practice-trend * { box-sizing:border-box; min-width:0; }
.trend-header { display:flex; align-items:end; justify-content:space-between; gap:24px; }
.trend-header>div:first-child { flex:1; }
.trend-header h2 { margin:4px 0; font-size:17px; line-height:1.4; letter-spacing:-.025em; }
.trend-header p { margin:0; color:var(--text-secondary); font-size:13px; overflow-wrap:anywhere; }
.range-switch { padding:4px; border:0; border-radius:var(--radius-md); background:var(--bg-sidebar); display:flex; flex:none; }
.range-switch button { min-width:44px; min-height:44px; padding:0 8px; border:0; border-radius:var(--radius-sm); color:var(--text-secondary); background:transparent; font-size:13px; cursor:pointer; }
.range-switch button.active { color:var(--text-primary); background:var(--surface-selected); font-weight:650; }
.trend-cards { margin-top:16px; display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px 24px; }
.trend-group-heading { grid-column:1/-1; margin:12px 0 0; color:var(--text-primary); font-size:17px; line-height:1.3; font-weight:630; }
.trend-group-heading:first-child { margin-top:0; }
.primary-cards.ei-plan { grid-template-columns:repeat(2,minmax(0,1fr)); }
.trend-cards article { padding:16px 0; border:0; border-bottom:1px solid var(--border-subtle); border-radius:0; background:transparent; display:grid; align-content:start; gap:8px; overflow-wrap:anywhere; }
.trend-cards small,.trend-cards span { color:var(--text-secondary); font-size:12px; line-height:1.4; }
.trend-cards strong { color:var(--text-primary); font-size:30px; font-weight:650; line-height:1.1; font-variant-numeric:tabular-nums; overflow-wrap:anywhere; }
.trend-cards strong em { margin-left:4px; color:var(--text-secondary); font-size:14px; font-style:normal; font-weight:500; }
.trend-cards i { height:4px; margin:4px 0; border-radius:4px; background:var(--border-default); }
.trend-cards i b { max-width:100%; height:100%; border-radius:inherit; background:var(--accent); display:block; }
.positive,.on-track { color:var(--mastered)!important; }
.negative,.behind { color:var(--danger)!important; }
.trend-controls { margin-top:16px; display:flex; align-items:center; flex-wrap:wrap; gap:8px 16px; }
.trend-controls>div { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.trend-controls span,.trend-controls label { color:var(--text-secondary); font-size:13px; }
.trend-controls button { min-height:44px; padding:0 12px; border:0; border-radius:var(--radius-sm); color:var(--text-secondary); background:transparent; font-size:13px; cursor:pointer; }
.trend-controls button.active { color:var(--text-primary); background:var(--surface-selected); font-weight:600; }
.trend-controls input { max-width:100%; height:44px; padding:0 8px; border:1px solid var(--border-default); border-radius:var(--radius-sm); color:var(--text-primary); background:var(--bg-elevated); font-size:16px; }
.trend-controls label input[type=number] { width:72px; margin-left:4px; }
.deadline-control { margin-left:auto; }
.trend-chart { width:100%; max-width:100%; height:320px; margin-top:24px; touch-action:pan-y; overflow:hidden; }
.trend-chart-heading { margin-top:24px; display:flex; align-items:center; justify-content:space-between; gap:16px; }
.trend-chart-heading h3 { margin:0; font-size:17px; }
.trend-chart-heading + .trend-chart { margin-top:12px; }
.chart-footnote { padding:12px 0 0; border-top:1px solid var(--border-subtle); color:var(--text-secondary); display:flex; flex-wrap:wrap; gap:8px 16px; font-size:12px; overflow-wrap:anywhere; font-variant-numeric:tabular-nums; }
.prediction-panel { margin-top:24px; padding-top:20px; border-top:1px solid var(--border-subtle); }
.prediction-panel>header { display:flex; align-items:end; justify-content:space-between; flex-wrap:wrap; gap:8px 16px; }
.prediction-panel h3 { margin:4px 0 0; font-size:17px; }
.prediction-panel>header>strong { font-size:14px; overflow-wrap:anywhere; }
.forecast-answer { margin-top:12px; display:flex; flex-wrap:wrap; gap:8px 24px; font-size:14px; color:var(--text-secondary); }
.forecast-answer b { color:var(--text-primary); font-variant-numeric:tabular-nums; }
.prediction-grid { margin-top:16px; display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px; }
.prediction-grid article { padding:16px 0; border:0; border-bottom:1px solid var(--border-subtle); border-radius:0; background:transparent; display:grid; align-content:start; gap:8px; overflow-wrap:anywhere; }
.prediction-grid small,.prediction-grid span { color:var(--text-secondary); font-size:12px; line-height:1.4; }
.prediction-grid strong { font-size:24px; font-weight:650; font-variant-numeric:tabular-nums; }
.prediction-grid strong em { margin-left:6px; color:var(--text-secondary); font-size:12px; font-style:normal; font-weight:500; }
.prediction-panel>p { margin:12px 0 0; color:var(--text-secondary); font-size:12px; overflow-wrap:anywhere; }
.trend-loading { min-height:180px; color:var(--text-secondary); display:grid; place-items:center; font-size:14px; }
.trend-error { padding:12px; color:var(--danger); font-size:13px; overflow-wrap:anywhere; }
.trend-error button { border:0; color:var(--text-primary); background:transparent; text-decoration:underline; cursor:pointer; }
.secondary-metrics { margin-top:20px; color:var(--text-secondary); font-size:13px; }
.secondary-metrics summary { cursor:pointer; padding:10px 0; }
.secondary-metrics .trend-cards strong { font-size:25px; }
.practice-trend button:focus-visible,.practice-trend input:focus-visible,.secondary-metrics summary:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
@media(max-width:820px) { .trend-header { align-items:start; flex-direction:column; gap:12px; } .range-switch { width:100%; } .range-switch button { flex:1; min-width:0; } .trend-chart-heading { align-items:start; flex-direction:column; } .trend-cards { grid-template-columns:repeat(2,minmax(0,1fr)); } .deadline-control { margin-left:0; } .trend-chart { height:285px; } .prediction-grid { grid-template-columns:1fr; } }
@media(max-width:430px) { .trend-header h2 { font-size:17px; } .trend-cards article { padding:12px 0; } .trend-cards strong { font-size:25px; } .trend-chart { height:260px; } .prediction-panel>header { align-items:start; flex-direction:column; } .trend-controls>div { width:100%; } .trend-controls .deadline-control>span { flex-basis:100%; } .deadline-control input[type=date] { flex:1 1 140px; } }
.chart-data { margin-top:12px; font-size:13px; color:var(--text-secondary); } .chart-data summary { min-height:44px; display:flex; align-items:center; cursor:pointer; } .chart-table-scroll { max-width:100%; overflow:auto; } .chart-data table { width:100%; border-collapse:collapse; font-size:13px; font-variant-numeric:tabular-nums; } .chart-data caption { text-align:left; padding:8px 0; } .chart-data th,.chart-data td { padding:8px; border-bottom:1px solid var(--border-subtle); text-align:right; white-space:nowrap; } .chart-data th:first-child { text-align:left; }
@container(max-width:520px) { .trend-cards,.primary-cards.ei-plan { grid-template-columns:minmax(0,1fr); } }
</style>
