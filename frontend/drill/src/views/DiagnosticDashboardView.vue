<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
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
const isEi = runtimeWorkspace === 'ei'
const title = computed(() => isEi ? 'EI 专业课 · 解题能力' : 'Drill 数学 · 解题能力')

function percentage(value: number | null) { return value === null ? '—' : `${value}%` }
function dailyRate(correct: number, sample: number) { return sample ? Math.round(correct * 1000 / sample) / 10 : null }
function css(name: string, fallback: string) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback }

function option(): EChartsCoreOption {
  const payload = data.value!
  const text = css('--text-tertiary', '#888')
  const border = css('--border-subtle', '#333')
  return {
    animationDuration: 220,
    grid: { left: 38, right: 16, top: 42, bottom: 30 },
    legend: { top: 3, textStyle: { color: text, fontSize: 10 }, data: ['首次独立正确率', '二次独立正确率'] },
    tooltip: {
      trigger: 'axis', confine: true,
      formatter(raw: unknown) {
        const rows = raw as Array<{ dataIndex: number; marker: string; seriesName: string; value: number | null }>
        const point = payload.trend[rows[0]?.dataIndex || 0]
        return [`<strong>${point.date}</strong>`, ...rows.map(row => `${row.marker}${row.seriesName}：${row.value === null ? '无样本' : `${row.value}%`}`), `首次样本：${point.first_sample}`, `二次样本：${point.second_sample}`].join('<br>')
      },
    },
    xAxis: { type: 'category', data: payload.trend.map(row => row.date.slice(5)), axisLine: { lineStyle: { color: border } }, axisLabel: { color: text, fontSize: 9 } },
    yAxis: { type: 'value', min: 0, max: 100, axisLabel: { color: text, formatter: '{value}%' }, splitLine: { lineStyle: { color: border, type: 'dashed' } } },
    series: [
      { name: '首次独立正确率', type: 'line', connectNulls: false, smooth: .25, data: payload.trend.map(row => dailyRate(row.first_independent_correct, row.first_sample)), lineStyle: { width: 2, color: '#15c878' }, itemStyle: { color: '#15c878' } },
      { name: '二次独立正确率', type: 'line', connectNulls: false, smooth: .25, data: payload.trend.map(row => dailyRate(row.second_independent_correct, row.second_sample)), lineStyle: { width: 2, color: '#e4b938' }, itemStyle: { color: '#e4b938' } },
    ],
  }
}

function activityOption(): EChartsCoreOption {
  const payload = data.value!
  const text = css('--text-tertiary', '#888')
  const border = css('--border-subtle', '#333')
  return {
    animationDuration: 220,
    grid: { left: 38, right: 14, top: 40, bottom: 38 },
    legend: { top: 3, textStyle: { color: text, fontSize: 10 }, data: ['每日去重题数', '提交次数'] },
    tooltip: {
      trigger: 'axis', confine: true,
      formatter(raw: unknown) {
        const rows = raw as Array<{ dataIndex: number; marker: string; seriesName: string; value: number }>
        const point = payload.activity[rows[0]?.dataIndex || 0]
        return [
          `<strong>${point.date}</strong>`,
          ...rows.map(row => `${row.marker}${row.seriesName}：${row.value}`),
          `新题：${point.new_questions}　复习：${point.review_questions}`,
          `有诊断证据：${point.diagnosed_questions}　历史未知：${point.legacy_unknown_questions}`,
        ].join('<br>')
      },
    },
    xAxis: { type: 'category', data: payload.activity.map(row => row.date.slice(5)), axisLine: { lineStyle: { color: border } }, axisLabel: { color: text, fontSize: 9, hideOverlap: true } },
    yAxis: { type: 'value', minInterval: 1, axisLabel: { color: text }, splitLine: { lineStyle: { color: border, type: 'dashed' } } },
    series: [
      { name: '每日去重题数', type: 'bar', barMaxWidth: 18, data: payload.activity.map(row => row.daily_unique_questions), itemStyle: { color: '#2f9ee5', borderRadius: [3, 3, 0, 0] } },
      { name: '提交次数', type: 'line', smooth: .2, data: payload.activity.map(row => row.submissions), lineStyle: { width: 2, color: '#e4b938' }, itemStyle: { color: '#e4b938' } },
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
  void load()
  resizeObserver = new ResizeObserver(() => { chart?.resize(); activityChart?.resize() })
  if (chartElement.value) resizeObserver.observe(chartElement.value)
  if (activityChartElement.value) resizeObserver.observe(activityChartElement.value)
})
onUnmounted(() => { resizeObserver?.disconnect(); chart?.dispose(); activityChart?.dispose() })
</script>

<template>
  <section class="page diagnostic-page">
    <header class="page-header diagnostic-header">
      <div><span class="eyebrow">ABILITY DIAGNOSIS</span><h1>{{ title }}</h1><p>区分“做过”与“能够独立做对”；所有比例均显示真实样本量。</p></div>
      <div class="range"><button v-for="value in [7,14,30]" :key="value" :class="{ active: days === value && !customStart }" @click="setDays(value)">{{ value }}天</button><label>自定<input v-model="customStart" type="date" /><input v-model="customEnd" type="date" /><button @click="applyCustomRange">应用</button></label></div>
    </header>
    <p v-if="error" class="error-state">{{ error }}</p>
    <div v-if="loading && !data" class="question-skeleton">正在计算诊断指标…</div>
    <template v-else-if="data">
      <section class="today-strip">
        <article><span>今日新题</span><strong>{{ data.today.new_questions }}</strong><small>首次有效作答</small></article>
        <article><span>今日复习</span><strong>{{ data.today.review_questions }}</strong><small>重做 / 巩固</small></article>
        <article><span>今日首次独立</span><strong>{{ data.today.first_independent_correct }}/{{ data.today.first_sample }}</strong><small>正确 / 样本</small></article>
        <button @click="openDue"><span>当前到期复习</span><strong>{{ data.due_count }}</strong><small>进入闭环队列 →</small></button>
      </section>

      <section class="ability-board activity-board">
        <header><h2>刷题活动</h2><span>包含功能上线前的真实历史记录</span></header>
        <div class="activity-summary">
          <article><small>本周期每日去重合计</small><strong>{{ data.period_activity.daily_unique_questions }}</strong><span>同题跨日分别计入</span></article>
          <article><small>本周期提交次数</small><strong>{{ data.period_activity.submissions }}</strong><span>保留重复提交</span></article>
          <article><small>不同题目</small><strong>{{ data.period_activity.unique_questions }}</strong><span>周期内按题去重</span></article>
          <article><small>历史诊断未知</small><strong>{{ data.period_activity.legacy_unknown_attempts }}</strong><span>计入题量，不推断独立性</span></article>
        </div>
        <div ref="activityChartElement" class="activity-chart" role="img" aria-label="每日去重刷题量与提交次数" />
        <p class="activity-note">蓝柱是每天完成的不同题目数；黄线是保存成功的提交次数。旧记录会显示题量，但不会被冒充为“独立正确”。</p>
      </section>

      <section class="ability-board">
        <header><h2>解题能力看板</h2><span>{{ data.range.start }} — {{ data.range.end }}</span></header>
        <div class="metric-grid">
          <article><small>首次独立正确率</small><strong>{{ percentage(data.metrics.first_independent_accuracy.value) }}</strong><span>{{ data.metrics.first_independent_accuracy.numerator }}/{{ data.metrics.first_independent_accuracy.sample }} 题</span></article>
          <article><small>二次独立正确率</small><strong>{{ percentage(data.metrics.second_independent_accuracy.value) }}</strong><span>{{ data.metrics.second_independent_accuracy.numerator }}/{{ data.metrics.second_independent_accuracy.sample }} 题</span></article>
          <button @click="openErrors(['B2','B3'])"><small>方法启动失败率</small><strong>{{ percentage(data.metrics.method_start_failure_rate.value) }}</strong><span>诊断样本 {{ data.metrics.method_start_failure_rate.sample }} · 查看题目 →</span></button>
          <article><small>错误复发率</small><strong>{{ percentage(data.metrics.error_recurrence_rate.value) }}</strong><span>可比较题目 {{ data.metrics.error_recurrence_rate.sample }}</span></article>
        </div>
        <h3>最近 7 天独立正确率趋势</h3>
        <div ref="chartElement" class="ability-chart" role="img" aria-label="首次与二次独立正确率趋势图" />
      </section>

      <div class="diagnostic-grid">
        <section class="error-distribution">
          <header><div><span class="eyebrow">ERROR PROFILE</span><h2>错误分布</h2></div><small>只统计有明确主错误的作答</small></header>
          <button v-for="row in data.error_distribution" :key="row.code" :disabled="!row.count" @click="openErrors([row.code])"><b>{{ row.code }}</b><span><i :style="{ width: `${Math.min(100, row.count * 10)}%` }" /></span><strong>{{ row.count }}</strong></button>
        </section>
        <section class="course-table">
          <header><div><span class="eyebrow">SUBJECTS / BOOKS</span><h2>{{ isEi ? '五大学科能力对比' : '题册能力对比' }}</h2></div></header>
          <div class="course-row heading"><span>学科 / 题册</span><span>首次独立</span><span>方法失败</span><span>重做通过</span></div>
          <div v-for="course in data.courses" :key="course.code" class="course-row"><strong>{{ course.label }}</strong><span>{{ percentage(course.first_independent_accuracy) }}<small>n={{ course.first_sample }}</small></span><span>{{ percentage(course.method_failure_rate) }}</span><span>{{ percentage(course.redo_pass_rate) }}<small>n={{ course.redo_sample }}</small></span></div>
          <p v-if="!data.courses.length">当前周期还没有带诊断信息的有效作答。</p>
        </section>
      </div>
      <div class="diagnostic-grid secondary-analysis">
        <section class="course-table"><header><div><span class="eyebrow">REPEATED ERRORS</span><h2>反复出错最多的知识点</h2></div></header><div v-for="row in data.repeated_topics" :key="row.topic" class="topic-analysis-row"><strong>{{ row.topic }}</strong><span>{{ row.diagnosed_errors }} 次明确错误</span></div><p v-if="!data.repeated_topics.length">暂无明确错误标签。</p></section>
        <section class="course-table"><header><div><span class="eyebrow">7D VS PREVIOUS 7D</span><h2>近期改善 / 恶化</h2></div></header><div v-for="row in data.topic_trends" :key="row.topic" class="topic-analysis-row"><strong>{{ row.topic }}</strong><span :class="row.change >= 0 ? 'improved' : 'worsened'">{{ row.change > 0 ? '+' : '' }}{{ row.change }}%</span><small>{{ row.previous_rate }}% (n={{ row.previous_sample }}) → {{ row.current_rate }}% (n={{ row.current_sample }})</small></div><p v-if="!data.topic_trends.length">两个比较窗口尚无足够显式独立作答样本。</p></section>
      </div>
      <p class="diagnostic-notice">{{ data.notice }}</p>
    </template>
  </section>
</template>

<style scoped>
.diagnostic-header{display:flex;align-items:end;justify-content:space-between;gap:16px}.diagnostic-header h1{margin:5px 0}.diagnostic-header p{margin:0;color:var(--text-tertiary);font-size:11px}.range{display:flex;align-items:center;padding:3px;border:1px solid var(--border-subtle);border-radius:7px}.range button{padding:7px 12px;border:0;border-radius:5px;color:var(--text-tertiary);background:transparent;cursor:pointer}.range button.active{color:var(--text-primary);background:var(--bg-surface-active)}.range label{display:flex;align-items:center;gap:4px;margin-left:3px;color:var(--text-tertiary);font-size:8px}.range input{width:118px;padding:5px;border:1px solid var(--border-subtle);border-radius:4px;color:var(--text-primary);background:var(--bg-sidebar);font-size:8px}.today-strip{margin:16px 0;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.today-strip article,.today-strip button{padding:13px;border:1px solid var(--border-subtle);border-radius:9px;color:var(--text-primary);background:var(--bg-surface);text-align:left;display:grid;gap:4px}.today-strip button{cursor:pointer}.today-strip span,.today-strip small{color:var(--text-tertiary);font-size:9px}.today-strip strong{font:650 24px ui-monospace,monospace}.ability-board{padding:16px;border:1px solid var(--border-subtle);border-radius:12px;background:var(--bg-surface)}.ability-board>header{display:flex;justify-content:space-between}.ability-board h2,.diagnostic-grid h2{margin:0;font-size:17px}.ability-board>header span{color:var(--text-tertiary);font-size:9px}.metric-grid{margin-top:12px;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.metric-grid article,.metric-grid button{min-height:96px;padding:13px;border:1px solid var(--border-subtle);border-radius:9px;color:var(--text-primary);background:var(--bg-sidebar);text-align:left;display:grid;gap:5px}.metric-grid button{cursor:pointer}.metric-grid small,.metric-grid span{color:var(--text-tertiary);font-size:10px}.metric-grid strong{font:650 27px ui-monospace,monospace}.ability-board h3{margin:16px 0 0;font-size:12px}.ability-chart{height:310px;width:100%;touch-action:pan-y}.diagnostic-grid{margin-top:12px;display:grid;grid-template-columns:minmax(260px,.8fr) minmax(420px,1.4fr);gap:12px}.error-distribution,.course-table{padding:15px;border:1px solid var(--border-subtle);border-radius:12px;background:var(--bg-surface)}.error-distribution>header,.course-table>header{display:flex;justify-content:space-between;align-items:end;margin-bottom:12px}.error-distribution>header small{color:var(--text-tertiary);font-size:8px}.error-distribution>button{width:100%;display:grid;grid-template-columns:30px 1fr 30px;align-items:center;gap:8px;padding:7px 0;border:0;color:var(--text-primary);background:transparent;text-align:left;cursor:pointer}.error-distribution>button:disabled{cursor:default;opacity:.45}.error-distribution>button span{height:5px;border-radius:4px;background:var(--border-subtle);overflow:hidden}.error-distribution>button i{display:block;height:100%;min-width:2px;background:#e0b238}.error-distribution>button strong{text-align:right}.course-row{display:grid;grid-template-columns:1.5fr repeat(3,1fr);align-items:center;gap:8px;padding:9px 3px;border-top:1px solid var(--border-subtle);font-size:10px}.course-row.heading{border:0;color:var(--text-tertiary);font-size:8px}.course-row>span{display:grid;gap:2px}.course-row small{color:var(--text-tertiary);font-size:8px}.course-table>p,.diagnostic-notice{color:var(--text-tertiary);font-size:9px}.diagnostic-notice{margin:10px 2px}.eyebrow{font-size:8px;color:var(--text-tertiary)}.secondary-analysis{grid-template-columns:repeat(2,minmax(0,1fr))}.topic-analysis-row{display:grid;grid-template-columns:1fr auto;gap:3px 10px;padding:9px 2px;border-top:1px solid var(--border-subtle);font-size:10px}.topic-analysis-row small{grid-column:1/-1;color:var(--text-tertiary);font-size:8px}.topic-analysis-row .improved{color:var(--success)}.topic-analysis-row .worsened{color:var(--danger)}
.activity-board{margin-bottom:12px}.activity-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:12px}.activity-summary article{display:grid;gap:4px;padding:11px;border:1px solid var(--border-subtle);border-radius:8px;background:var(--bg-sidebar)}.activity-summary small,.activity-summary span,.activity-note{color:var(--text-tertiary);font-size:9px}.activity-summary strong{font:650 22px ui-monospace,monospace}.activity-chart{width:100%;height:260px;touch-action:pan-y}.activity-note{margin:0}
@media(max-width:800px){.diagnostic-header{align-items:start;flex-direction:column}.range{width:100%;flex-wrap:wrap}.range>button{flex:1}.range label{width:100%;margin-top:3px}.range input{flex:1;min-width:0}.today-strip,.activity-summary{grid-template-columns:repeat(2,minmax(0,1fr))}.diagnostic-grid,.secondary-analysis{grid-template-columns:1fr}.ability-chart{height:270px}.activity-chart{height:240px}.course-row{grid-template-columns:1.4fr repeat(3,.8fr)}}@media(max-width:430px){.metric-grid{grid-template-columns:1fr}.course-row{font-size:9px;gap:4px}.today-strip strong{font-size:20px}}
</style>
