<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { EChartsType } from '../lib/charts'
import type { Overview } from '../types'

const props = defineProps<{ overview: Overview | null }>()
const chartEl = ref<HTMLElement | null>(null)
let chart: EChartsType | null = null

function minuteToTime(value: number) {
  const normalized = Math.max(0, Math.min(1439, value))
  return `${Math.floor(normalized / 60).toString().padStart(2, '0')}:${Math.round(normalized % 60).toString().padStart(2, '0')}`
}

async function draw() {
  if (!chartEl.value || !props.overview) return
  const echarts = await import('../lib/charts')
  chart = echarts.init(chartEl.value, undefined, { renderer: 'canvas' })
  const recent = props.overview.heatmap.slice(-60)
  const starts = recent.map((row) => row.first_start ? Number(row.first_start.slice(0, 2)) * 60 + Number(row.first_start.slice(3, 5)) : null)
  chart.setOption({
    backgroundColor: 'transparent',
    animationDuration: 450,
    tooltip: { trigger: 'axis', backgroundColor: '#111511', borderColor: '#353b36', textStyle: { color: '#f1f4f2' }, formatter(params: Array<{ axisValue: string; seriesName: string; value: number | null; marker: string }>) { return `${params[0]?.axisValue}<br/>${params.map((p) => `${p.marker}${p.seriesName}: ${p.seriesName === 'First start' && p.value != null ? minuteToTime(p.value) : `${p.value || 0} min`}`).join('<br/>')}` } },
    legend: { data: ['Duration', 'First start'], textStyle: { color: '#929b96' }, top: 0 },
    grid: { left: 45, right: 50, top: 45, bottom: 35 },
    xAxis: { type: 'category', data: recent.map((r) => r.date.slice(5)), axisLabel: { color: '#789086', interval: 6 }, axisLine: { lineStyle: { color: '#254036' } } },
    yAxis: [
      { type: 'value', name: 'MIN', nameTextStyle: { color: '#737d77' }, axisLabel: { color: '#737d77' }, splitLine: { lineStyle: { color: '#242a26' } } },
      { type: 'value', min: 300, max: 900, inverse: true, interval: 120, axisLabel: { color: '#789086', formatter: (v: number) => minuteToTime(v) }, splitLine: { show: false } },
    ],
    series: [
      { name: 'Duration', type: 'bar', data: recent.map((r) => r.minutes), barMaxWidth: 12, itemStyle: { color: (p: { data: number }) => p.data >= 300 ? '#f0a7ff' : '#6f59d9', borderRadius: [2, 2, 0, 0] }, markLine: { silent: true, symbol: 'none', label: { color: '#f0a7ff', formatter: '5H' }, lineStyle: { color: '#f0a7ff', type: 'dashed', opacity: 0.45 }, data: [{ yAxis: 300 }] } },
      { name: 'First start', type: 'line', yAxisIndex: 1, data: starts, connectNulls: false, showSymbol: false, smooth: 0.25, lineStyle: { color: '#6ad7ff', width: 2 }, itemStyle: { color: '#6ad7ff' } },
    ],
  })
}

function resize() { chart?.resize() }
onMounted(async () => { await nextTick(); await draw(); window.addEventListener('resize', resize, { passive: true }) })
watch(() => props.overview, async (value) => {
  if (!value) return
  await nextTick()
  chart?.dispose()
  chart = null
  await draw()
})
onBeforeUnmount(() => { window.removeEventListener('resize', resize); chart?.dispose() })
</script>

<template>
  <div class="view-stack">
    <section class="page-intro"><span class="eyebrow">TRENDS / 60 DAYS</span><h1>Study trends</h1><p>Completed duration and first session start time by day.</p></section>
    <section class="panel chart-panel"><div class="chart-toolbar"><div><span class="analysis-chip active">Duration</span><span class="analysis-chip">First start</span></div><b>DAILY · 60D</b></div><div ref="chartEl" class="trend-chart" /></section>
    <section class="insight-grid" v-if="overview">
      <article class="panel insight"><span>AVERAGE FIRST START</span><strong>{{ overview.summary.average_start_time || '--' }}</strong><p>Active days only</p></article>
      <article class="panel insight goal"><span>5H TARGET DAYS</span><strong>{{ overview.summary.five_hour_days }}</strong><p>{{ overview.summary.current_five_hour_streak }}-day current streak</p></article>
      <article class="panel insight"><span>TOTAL COMPLETED</span><strong>{{ Math.floor(overview.summary.total_minutes / 60) }}h</strong><p>{{ overview.summary.session_count }} sessions</p></article>
    </section>
    <section v-if="overview" class="aggregate-grid">
      <article class="panel aggregate-card"><span class="eyebrow">WEEKLY BREAKDOWN</span><h2>Recent weeks</h2><div v-for="row in overview.weekly_totals.slice(-6).reverse()" :key="row.week_start"><span>{{ row.week_start }}</span><b>{{ Math.floor(row.minutes / 60) }}h {{ row.minutes % 60 }}m</b></div></article>
      <article class="panel aggregate-card"><span class="eyebrow">MONTHLY BREAKDOWN</span><h2>Recent months</h2><div v-for="row in overview.monthly_totals.slice(-6).reverse()" :key="row.month"><span>{{ row.month }}</span><b>{{ Math.floor(row.minutes / 60) }}h {{ row.minutes % 60 }}m</b></div></article>
      <article class="panel aggregate-card tag-stat-list"><span class="eyebrow">TAG BREAKDOWN</span><h2>Reusable content tags</h2><div v-for="row in overview.tag_totals.slice(0, 10)" :key="row.id"><span>#{{ row.name }}</span><small>{{ row.sessions }} sessions</small><b>{{ Math.floor(row.minutes / 60) }}h {{ row.minutes % 60 }}m</b></div><p v-if="!overview.tag_totals.length" class="section-note">No tagged Sessions yet.</p></article>
      <article class="panel aggregate-card tag-stat-list"><span class="eyebrow">TASK BREAKDOWN</span><h2>Preset paths</h2><div v-for="row in overview.task_totals.slice(0, 10)" :key="`${row.subject}:${row.path}`"><span>{{ row.subject_label }} · {{ row.path }}</span><small>{{ row.sessions }} sessions</small><b>{{ Math.floor(row.minutes / 60) }}h {{ row.minutes % 60 }}m</b></div><p v-if="!overview.task_totals.length" class="section-note">No preset Sessions yet.</p></article>
    </section>
  </div>
</template>
