<script setup lang="ts">
import { uiText } from '../lib/uiText'
import { uiLanguage } from '../lib/uiPreferences'
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { ECharts, EChartsCoreOption } from 'echarts/core'
import { api } from '../lib/api'
import type { DiagnosticDashboard, ErrorCode } from '../types'
import { runtimeWorkspace } from '../lib/runtimePath'

echarts.use([BarChart, LineChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer])

const router = useRouter()
const data = ref<DiagnosticDashboard | null>(null)
const loading = ref(true)
const error = ref('')
const days = ref(7)
const customStart = ref('')
const customEnd = ref('')
const chartElement = ref<HTMLElement | null>(null)
const activityChartElement = ref<HTMLElement | null>(null)
let chart: ECharts | null = null
let activityChart: ECharts | null = null
let resizeObserver: ResizeObserver | null = null
let resizeFrame = 0
const isEi = runtimeWorkspace === 'ei'
const title = computed(() => isEi ? uiText("EI 专业课 · 解题能力") : uiText("Drill 数学 · 解题能力"))

function percentage(value: number | null) { return value === null ? '—' : `${value}%` }
function dailyRate(correct: number, sample: number) { return sample ? Math.round(correct * 1000 / sample) / 10 : null }
function css(name: string, fallback: string) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback }

function option(): EChartsCoreOption {
  const payload = data.value!
  const text = css('--text-secondary', '#a3a3ab')
  const border = css('--border-subtle', '#242429')
  return {
    animationDuration: 220,
    grid: { left: 38, right: 16, top: 42, bottom: 30 },
    legend: { top: 3, textStyle: { color: text, fontSize: 12 }, data: [uiText("首次独立正确率"), uiText("二次独立正确率")] },
    tooltip: {
      trigger: 'axis', confine: true,
      formatter(raw: unknown) {
        const rows = raw as Array<{ dataIndex: number; marker: string; seriesName: string; value: number | null }>
        const point = payload.trend[rows[0]?.dataIndex || 0]
        return [`<strong>${point.date}</strong>`, ...rows.map(row => `${row.marker}${row.seriesName}：${row.value === null ? uiText("无样本") : `${row.value}%`}`), `${uiText("首次样本")}：${point.first_sample}`, `${uiText("二次样本")}：${point.second_sample}`].join('<br>')
      },
    },
    xAxis: { type: 'category', data: payload.trend.map(row => row.date.slice(5)), axisLine: { lineStyle: { color: border } }, axisLabel: { color: text, fontSize: 11, hideOverlap: true } },
    yAxis: { type: 'value', min: 0, max: 100, axisLabel: { color: text, fontSize: 11, formatter: '{value}%' }, splitLine: { lineStyle: { color: border, type: 'dashed' } } },
    series: [
      { name: uiText("首次独立正确率"), type: 'line', connectNulls: false, smooth: .25, data: payload.trend.map(row => dailyRate(row.first_independent_correct, row.first_sample)), lineStyle: { width: 2, color: css('--accent', '#55b88a') }, itemStyle: { color: css('--accent', '#55b88a') } },
      { name: uiText("二次独立正确率"), type: 'line', connectNulls: false, smooth: .25, data: payload.trend.map(row => dailyRate(row.second_independent_correct, row.second_sample)), lineStyle: { width: 2, color: css('--warning', '#d5a44f') }, itemStyle: { color: css('--warning', '#d5a44f') } },
    ],
  }
}

function activityOption(): EChartsCoreOption {
  const payload = data.value!
  const text = css('--text-secondary', '#a3a3ab')
  const border = css('--border-subtle', '#242429')
  return {
    animationDuration: 220,
    grid: { left: 38, right: 14, top: 40, bottom: 38 },
    legend: { top: 3, textStyle: { color: text, fontSize: 10 }, data: [uiText("每日去重题数"), uiText("提交次数")] },
    tooltip: {
      trigger: 'axis', confine: true,
      formatter(raw: unknown) {
        const rows = raw as Array<{ dataIndex: number; marker: string; seriesName: string; value: number }>
        const point = payload.activity[rows[0]?.dataIndex || 0]
        return [
          `<strong>${point.date}</strong>`,
          ...rows.map(row => `${row.marker}${row.seriesName}：${row.value}`),
          `${uiText("新题")}：${point.new_questions}　${uiText("复习")}：${point.review_questions}`,
          `${uiText("有诊断证据")}：${point.diagnosed_questions}　${uiText("历史未知")}：${point.legacy_unknown_questions}`,
        ].join('<br>')
      },
    },
    xAxis: { type: 'category', data: payload.activity.map(row => row.date.slice(5)), axisLine: { lineStyle: { color: border } }, axisLabel: { color: text, fontSize: 11, hideOverlap: true } },
    yAxis: { type: 'value', minInterval: 1, axisLabel: { color: text, fontSize: 11 }, splitLine: { lineStyle: { color: border, type: 'dashed' } } },
    series: [
      { name: uiText("每日去重题数"), type: 'bar', barMaxWidth: 18, data: payload.activity.map(row => row.daily_unique_questions), itemStyle: { color: css('--accent', '#6ba6ff'), borderRadius: [3, 3, 0, 0] } },
      { name: uiText("提交次数"), type: 'line', smooth: .2, data: payload.activity.map(row => row.submissions), lineStyle: { width: 2, color: css('--warning', '#d5a44f') }, itemStyle: { color: css('--warning', '#d5a44f') } },
    ],
  }
}

async function renderChart() {
  await nextTick()
  if (!data.value || !chartElement.value) return
  chart ||= echarts.init(chartElement.value)
  chart.setOption(option(), true)
  if (activityChartElement.value) {
    activityChart ||= echarts.init(activityChartElement.value)
    activityChart.setOption(activityOption(), true)
  }
  scheduleResize()
}

function scheduleResize() {
  if (resizeFrame) window.cancelAnimationFrame(resizeFrame)
  resizeFrame = window.requestAnimationFrame(() => {
    resizeFrame = 0
    chart?.resize()
    activityChart?.resize()
  })
}

function observeChartElements() {
  if (!resizeObserver) return
  if (chartElement.value) resizeObserver.observe(chartElement.value)
  if (activityChartElement.value) resizeObserver.observe(activityChartElement.value)
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const params = customStart.value && customEnd.value
      ? new URLSearchParams({ start: customStart.value, end: customEnd.value })
      : new URLSearchParams({ days: String(days.value) })
    data.value = await api<DiagnosticDashboard>(`/api/drill/diagnostics/?${params}`)
    await renderChart()
  } catch (reason) {
    error.value = (reason as Error).message
  } finally { loading.value = false }
}

function setDays(value: number) { days.value = value; customStart.value = ''; customEnd.value = ''; void load() }
function applyCustomRange() { if (customStart.value && customEnd.value) void load() }
function openErrors(codes: ErrorCode[]) { void router.push({ path: '/diagnostic-queue', query: { error: codes.join(',') } }) }
function openDue() { void router.push({ path: '/diagnostic-queue', query: { queue: 'due' } }) }

onMounted(() => {
  resizeObserver = new ResizeObserver(() => { chart?.resize(); activityChart?.resize() })
  void load()
  void nextTick(observeChartElements)
  window.addEventListener('resize', scheduleResize)
  window.addEventListener('orientationchange', scheduleResize)
  window.addEventListener('pageshow', scheduleResize)
  window.visualViewport?.addEventListener('resize', scheduleResize)
})
onUnmounted(() => {
  resizeObserver?.disconnect(); chart?.dispose(); activityChart?.dispose()
  window.cancelAnimationFrame(resizeFrame)
  window.removeEventListener('resize', scheduleResize)
  window.removeEventListener('orientationchange', scheduleResize)
  window.removeEventListener('pageshow', scheduleResize)
  window.visualViewport?.removeEventListener('resize', scheduleResize)
})

watch([chartElement, activityChartElement], observeChartElements, { flush: 'post' })

watch(uiLanguage, () => { void renderChart() })
</script>

<template>
  <section class="page diagnostic-page">
    <header class="page-header diagnostic-header">
      <div><span class="eyebrow">ABILITY DIAGNOSIS</span><h1>{{ title }}</h1><p>{{ uiText("区分“做过”与“能够独立做对”；所有比例均显示真实样本量。") }}</p></div>
      <div class="range"><button v-for="value in [7,14,30]" :key="value" :class="{ active: days === value && !customStart }" @click="setDays(value)">{{ value }}{{ uiText("天") }}</button><label>{{ uiText("自定") }}<input v-model="customStart" type="date" /><input v-model="customEnd" type="date" /><button @click="applyCustomRange">{{ uiText("应用") }}</button></label></div>
    </header>
    <p v-if="error" class="error-state">{{ uiText(error) }}</p>
    <div v-if="loading && !data" class="question-skeleton">{{ uiText("正在计算诊断指标…") }}</div>
    <template v-else-if="data">
      <section class="today-strip">
        <article><span>{{ uiText("今日新题") }}</span><strong>{{ data.today.new_questions }}</strong><small>{{ uiText("首次有效作答") }}</small></article>
        <article><span>{{ uiText("今日复习") }}</span><strong>{{ data.today.review_questions }}</strong><small>{{ uiText("重做 / 巩固") }}</small></article>
        <article><span>{{ uiText("今日首次独立") }}</span><strong>{{ data.today.first_independent_correct }}/{{ data.today.first_sample }}</strong><small>{{ uiText("正确 / 样本") }}</small></article>
        <button @click="openDue"><span>{{ uiText("当前到期复习") }}</span><strong>{{ data.due_count }}</strong><small>{{ uiText("进入闭环队列 →") }}</small></button>
      </section>

      <section class="ability-board activity-board">
        <header><h2>{{ uiText("刷题活动") }}</h2><span>{{ uiText("包含功能上线前的真实历史记录") }}</span></header>
        <div class="activity-summary">
          <article><small>{{ uiText("本周期每日去重合计") }}</small><strong>{{ data.period_activity.daily_unique_questions }}</strong><span>{{ uiText("同题跨日分别计入") }}</span></article>
          <article><small>{{ uiText("本周期提交次数") }}</small><strong>{{ data.period_activity.submissions }}</strong><span>{{ uiText("保留重复提交") }}</span></article>
          <article><small>{{ uiText("不同题目") }}</small><strong>{{ data.period_activity.unique_questions }}</strong><span>{{ uiText("周期内按题去重") }}</span></article>
          <article><small>{{ uiText("历史诊断未知") }}</small><strong>{{ data.period_activity.legacy_unknown_attempts }}</strong><span>{{ uiText("计入题量，不推断独立性") }}</span></article>
        </div>
        <div ref="activityChartElement" class="activity-chart" role="img" :aria-label="uiText('每日去重刷题量与提交次数')" />
        <p class="activity-note">{{ uiText("蓝柱是每天完成的不同题目数；黄线是保存成功的提交次数。旧记录会显示题量，但不会被冒充为“独立正确”。") }}</p>
      </section>

      <section class="ability-board">
        <header><h2>{{ uiText("解题能力看板") }}</h2><span>{{ data.range.start }} — {{ data.range.end }}</span></header>
        <div class="metric-grid">
          <article><small>{{ uiText("首次独立正确率") }}</small><strong>{{ percentage(data.metrics.first_independent_accuracy.value) }}</strong><span>{{ data.metrics.first_independent_accuracy.numerator }}/{{ data.metrics.first_independent_accuracy.sample }} {{ uiText("题") }}</span></article>
          <article><small>{{ uiText("二次独立正确率") }}</small><strong>{{ percentage(data.metrics.second_independent_accuracy.value) }}</strong><span>{{ data.metrics.second_independent_accuracy.numerator }}/{{ data.metrics.second_independent_accuracy.sample }} {{ uiText("题") }}</span></article>
          <button @click="openErrors(['B2','B3'])"><small>{{ uiText("方法启动失败率") }}</small><strong>{{ percentage(data.metrics.method_start_failure_rate.value) }}</strong><span>{{ uiText("诊断样本") }} {{ data.metrics.method_start_failure_rate.sample }} {{ uiText("· 查看题目 →") }}</span></button>
          <article><small>{{ uiText("错误复发率") }}</small><strong>{{ percentage(data.metrics.error_recurrence_rate.value) }}</strong><span>{{ uiText("可比较题目") }} {{ data.metrics.error_recurrence_rate.sample }}</span></article>
        </div>
        <h3>{{ uiText("最近 7 天独立正确率趋势") }}</h3>
        <div ref="chartElement" class="ability-chart" role="img" :aria-label="uiText('首次与二次独立正确率趋势图')" />
      </section>

      <div class="diagnostic-grid">
        <section class="error-distribution">
          <header><div><span class="eyebrow">ERROR PROFILE</span><h2>{{ uiText("错误分布") }}</h2></div><small>{{ uiText("只统计有明确主错误的作答") }}</small></header>
          <button v-for="row in data.error_distribution" :key="row.code" :disabled="!row.count" @click="openErrors([row.code])"><b>{{ row.code }}</b><span><i :style="{ width: `${Math.min(100, row.count * 10)}%` }" /></span><strong>{{ row.count }}</strong></button>
        </section>
        <section class="course-table">
          <header><div><span class="eyebrow">SUBJECTS / BOOKS</span><h2>{{ isEi ? uiText("五大学科能力对比") : uiText("题册能力对比") }}</h2></div></header>
          <div class="course-row heading"><span>{{ uiText("学科 / 题册") }}</span><span>{{ uiText("首次独立") }}</span><span>{{ uiText("方法失败") }}</span><span>{{ uiText("重做通过") }}</span></div>
          <div v-for="course in data.courses" :key="course.code" class="course-row"><strong>{{ course.label }}</strong><span>{{ percentage(course.first_independent_accuracy) }}<small>n={{ course.first_sample }}</small></span><span>{{ percentage(course.method_failure_rate) }}</span><span>{{ percentage(course.redo_pass_rate) }}<small>n={{ course.redo_sample }}</small></span></div>
          <p v-if="!data.courses.length">{{ uiText("当前周期还没有带诊断信息的有效作答。") }}</p>
        </section>
      </div>
      <div class="diagnostic-grid secondary-analysis">
        <section class="course-table"><header><div><span class="eyebrow">REPEATED ERRORS</span><h2>{{ uiText("反复出错最多的知识点") }}</h2></div></header><div v-for="row in data.repeated_topics" :key="row.topic" class="topic-analysis-row"><strong>{{ row.topic }}</strong><span>{{ row.diagnosed_errors }} {{ uiText("次明确错误") }}</span></div><p v-if="!data.repeated_topics.length">{{ uiText("暂无明确错误标签。") }}</p></section>
        <section class="course-table"><header><div><span class="eyebrow">7D VS PREVIOUS 7D</span><h2>{{ uiText("近期改善 / 恶化") }}</h2></div></header><div v-for="row in data.topic_trends" :key="row.topic" class="topic-analysis-row"><strong>{{ row.topic }}</strong><span :class="row.change >= 0 ? 'improved' : 'worsened'">{{ row.change > 0 ? '+' : '' }}{{ row.change }}%</span><small>{{ row.previous_rate }}% (n={{ row.previous_sample }}) → {{ row.current_rate }}% (n={{ row.current_sample }})</small></div><p v-if="!data.topic_trends.length">{{ uiText("两个比较窗口尚无足够显式独立作答样本。") }}</p></section>
      </div>
      <p class="diagnostic-notice">{{ data.notice }}</p>
    </template>
  </section>
</template>

<style scoped>
.diagnostic-page{min-width:0}
.diagnostic-header{display:flex;align-items:end;justify-content:space-between;gap:24px}
.diagnostic-header h1{margin:6px 0;font-size:26px;line-height:1.2;letter-spacing:-.025em}
.diagnostic-header p{margin:0;color:var(--text-secondary);font-size:14px;line-height:1.5}
.eyebrow{font-size:11px;letter-spacing:.08em;color:var(--text-tertiary)}
.range{display:flex;align-items:center;gap:3px;padding:3px;border:1px solid var(--border-subtle);border-radius:var(--radius-sm);background:var(--bg-sidebar)}
.range button{min-height:40px;padding:0 13px;border:0;border-radius:5px;color:var(--text-secondary);background:transparent;font-size:13px;cursor:pointer}
.range button.active{color:var(--text-primary);background:var(--bg-surface-active)}
.range label{display:flex;align-items:center;gap:6px;margin-left:4px;color:var(--text-secondary);font-size:13px}
.range input{width:132px;min-height:40px;padding:0 8px;border:1px solid var(--border-subtle);border-radius:5px;color:var(--text-primary);background:var(--bg-surface);font-size:13px}
.today-strip{margin:20px 0;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.today-strip article,.today-strip button{min-width:0;padding:16px;border:1px solid var(--border-subtle);border-radius:var(--radius-sm);color:var(--text-primary);background:var(--bg-surface);text-align:left;display:grid;align-content:start;gap:7px}
.today-strip button{cursor:pointer;transition:border-color .15s ease}.today-strip button:hover{border-color:var(--accent)}
.today-strip span,.today-strip small{color:var(--text-secondary);font-size:13px;line-height:1.4}
.today-strip strong{font:650 30px/1.1 ui-monospace,monospace;font-variant-numeric:tabular-nums}
.ability-board{min-width:0;margin-top:16px;padding:18px 0;border-top:1px solid var(--border-subtle)}
.ability-board>header{display:flex;justify-content:space-between;align-items:baseline;gap:12px}
.ability-board h2,.diagnostic-grid h2{margin:0;font-size:18px;line-height:1.35}
.ability-board>header span{color:var(--text-secondary);font-size:13px;font-variant-numeric:tabular-nums}
.metric-grid{margin-top:14px;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.metric-grid article,.metric-grid button{min-width:0;min-height:108px;padding:15px;border:1px solid var(--border-subtle);border-radius:var(--radius-sm);color:var(--text-primary);background:var(--bg-surface);text-align:left;display:grid;align-content:start;gap:8px}
.metric-grid button{cursor:pointer;transition:border-color .15s ease}.metric-grid button:hover{border-color:var(--accent)}
.metric-grid small,.metric-grid span{color:var(--text-secondary);font-size:13px;line-height:1.4}
.metric-grid strong{font:650 30px/1.1 ui-monospace,monospace;font-variant-numeric:tabular-nums}
.ability-board h3{margin:22px 0 4px;font-size:15px}
.ability-chart{display:block;min-width:0;width:100%;height:310px;touch-action:pan-y;overflow:hidden}
.diagnostic-grid{min-width:0;margin-top:16px;display:grid;grid-template-columns:minmax(260px,.8fr) minmax(0,1.4fr);gap:24px}
.error-distribution,.course-table{min-width:0;padding:16px 0;border-top:1px solid var(--border-subtle);background:transparent}
.error-distribution>header,.course-table>header{display:flex;justify-content:space-between;align-items:end;gap:12px;margin-bottom:14px}
.error-distribution>header small{color:var(--text-secondary);font-size:12px}
.error-distribution>button{width:100%;min-height:42px;display:grid;grid-template-columns:36px minmax(0,1fr) 40px;align-items:center;gap:12px;padding:7px 4px;border:0;border-bottom:1px solid var(--border-subtle);color:var(--text-primary);background:transparent;text-align:left;cursor:pointer}
.error-distribution>button:disabled{cursor:default;opacity:.5}
.error-distribution>button b,.error-distribution>button strong{font-size:14px;font-variant-numeric:tabular-nums}
.error-distribution>button span{height:6px;border-radius:4px;background:var(--bg-elevated);overflow:hidden}
.error-distribution>button i{display:block;height:100%;min-width:2px;background:var(--warning);border-radius:inherit}
.error-distribution>button strong{text-align:right}
.course-row{min-width:0;display:grid;grid-template-columns:minmax(140px,1.5fr) repeat(3,minmax(0,1fr));align-items:center;gap:12px;padding:11px 4px;border-top:1px solid var(--border-subtle);font-size:13px}
.course-row.heading{border:0;color:var(--text-secondary);font-size:12px}
.course-row>span{display:grid;gap:4px}.course-row small{color:var(--text-tertiary);font-size:12px}
.course-table>p,.diagnostic-notice{color:var(--text-secondary);font-size:13px;line-height:1.5}
.secondary-analysis{grid-template-columns:repeat(2,minmax(0,1fr))}
.topic-analysis-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:5px 14px;padding:12px 4px;border-top:1px solid var(--border-subtle);font-size:14px}
.topic-analysis-row small{grid-column:1/-1;color:var(--text-secondary);font-size:12px;font-variant-numeric:tabular-nums}
.topic-analysis-row .improved{color:var(--success)}.topic-analysis-row .worsened{color:var(--danger)}
.diagnostic-notice{margin:16px 0}
.activity-board{margin-bottom:4px}
.activity-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-top:14px}
.activity-summary article{min-width:0;display:grid;align-content:start;gap:7px;padding:14px;border-left:2px solid var(--border-default);background:transparent}
.activity-summary small,.activity-summary span,.activity-note{color:var(--text-secondary);font-size:13px;line-height:1.45}
.activity-summary strong{font:650 27px/1.1 ui-monospace,monospace;font-variant-numeric:tabular-nums}
.activity-chart{display:block;min-width:0;width:100%;height:270px;touch-action:pan-y;overflow:hidden}
.activity-note{margin:4px 0 0}
@media(max-width:1100px){.diagnostic-header{align-items:start;flex-direction:column}.range{width:100%;flex-wrap:wrap}.range>button{flex:1}.range label{width:100%;margin:4px 0 0}.range input{flex:1;min-width:0}.today-strip,.activity-summary{grid-template-columns:repeat(2,minmax(0,1fr))}.metric-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.diagnostic-grid,.secondary-analysis{grid-template-columns:1fr;gap:12px}.ability-chart{height:280px}.activity-chart{height:250px}.course-row{grid-template-columns:minmax(130px,1.3fr) repeat(3,minmax(0,.8fr))}}
@media(max-width:600px){.diagnostic-header h1{font-size:23px}.diagnostic-header p{font-size:13px}.today-strip,.activity-summary{gap:8px}.today-strip article,.today-strip button{padding:12px}.today-strip strong{font-size:25px}.ability-board{padding:16px 0}.ability-board>header{align-items:start;flex-direction:column;gap:5px}.metric-grid{gap:8px}.metric-grid article,.metric-grid button{min-height:100px;padding:12px}.metric-grid strong{font-size:25px}.course-row{grid-template-columns:minmax(105px,1.15fr) repeat(3,minmax(0,.8fr));gap:5px;padding:10px 2px;font-size:12px}.course-row.heading{font-size:11px}.course-row small{font-size:11px}.error-distribution>header{align-items:start;flex-direction:column}.ability-chart{height:265px}.activity-chart{height:235px}}
@media(max-width:380px){.today-strip,.activity-summary,.metric-grid{grid-template-columns:1fr}.range label{flex-wrap:wrap}.range input{width:calc(50% - 4px);flex:1 1 40%}.course-row{grid-template-columns:minmax(90px,1.1fr) repeat(3,minmax(0,.75fr));font-size:11px}.course-row.heading{font-size:10px}}
</style>
