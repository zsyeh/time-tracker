<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { EChartsType } from '../lib/charts'
import { buildSubjectTimeStats } from '../lib/subjectStats'
import type { Overview } from '../types'

const props = defineProps<{ overview: Overview | null }>()
const chartEl = ref<HTMLElement | null>(null)
const chartMetric = ref<'duration' | 'start'>('duration')
const trackedSubjectStats = computed(() => buildSubjectTimeStats(props.overview))
let chart: EChartsType | null = null
let resizeObserver: ResizeObserver | null = null

function minuteToTime(value: number) {
  const normalized = Math.max(0, Math.min(1439, value))
  return `${Math.floor(normalized / 60).toString().padStart(2, '0')}:${Math.round(normalized % 60).toString().padStart(2, '0')}`
}

async function draw() {
  if (!chartEl.value || !props.overview) return
  const echarts = await import('../lib/charts')
  if (!chart) chart = echarts.init(chartEl.value, undefined, { renderer: 'canvas' })
  const recent = props.overview.heatmap.slice(-60)
  const starts = recent.map((row) => row.first_start ? Number(row.first_start.slice(0, 2)) * 60 + Number(row.first_start.slice(3, 5)) : null)
  const styles = getComputedStyle(document.documentElement)
  const accent = styles.getPropertyValue('--accent').trim() || '#8b7cf6'
  const secondary = styles.getPropertyValue('--chart-secondary').trim() || '#7d8590'
  const border = styles.getPropertyValue('--border-subtle').trim() || '#25262b'
  const tertiary = styles.getPropertyValue('--text-tertiary').trim() || '#747780'
  const surface = styles.getPropertyValue('--bg-elevated').trim() || '#17171a'
  const primaryText = styles.getPropertyValue('--text-primary').trim() || '#e6e6e8'
  const showDuration = chartMetric.value === 'duration'
  chart.setOption({
    backgroundColor: 'transparent',
    animationDuration: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 180,
    tooltip: { trigger: 'axis', backgroundColor: surface, borderColor: border, padding: 10, textStyle: { color: primaryText, fontSize: 12 }, formatter(params: Array<{ axisValue: string; seriesName: string; value: number | null; marker: string }>) { return `${params[0]?.axisValue}<br/>${params.map((p) => `${p.marker}${p.seriesName}: ${p.seriesName === 'First start' && p.value != null ? minuteToTime(p.value) : `${p.value || 0} min`}`).join('<br/>')}` } },
    grid: { left: 48, right: showDuration ? 18 : 48, top: 20, bottom: 30 },
    xAxis: { type: 'category', data: recent.map((r) => r.date.slice(5)), axisLabel: { color: tertiary, interval: 6 }, axisTick: { show: false }, axisLine: { lineStyle: { color: border } } },
    yAxis: [
      { show: showDuration, type: 'value', axisLabel: { color: tertiary }, axisTick: { show: false }, axisLine: { show: false }, splitLine: { lineStyle: { color: border } } },
      { show: !showDuration, type: 'value', min: 300, max: 900, inverse: true, interval: 120, axisLabel: { color: tertiary, formatter: (v: number) => minuteToTime(v) }, axisTick: { show: false }, axisLine: { show: false }, splitLine: { lineStyle: { color: border } } },
    ],
    series: showDuration
      ? [{ name: 'Duration', type: 'bar', data: recent.map((r) => r.minutes), barMaxWidth: 10, itemStyle: { color: (p: { data: number }) => p.data >= 300 ? accent : secondary, borderRadius: [2, 2, 0, 0] }, markLine: { silent: true, symbol: 'none', label: { color: tertiary, formatter: '5h target' }, lineStyle: { color: accent, type: 'dashed', opacity: 0.35 }, data: [{ yAxis: 300 }] } }]
      : [{ name: 'First start', type: 'line', yAxisIndex: 1, data: starts, connectNulls: false, showSymbol: false, smooth: 0.18, lineStyle: { color: accent, width: 2 }, itemStyle: { color: accent }, areaStyle: { color: accent, opacity: 0.035 } }],
  }, true)
}

onMounted(async () => {
  await nextTick()
  await draw()
  if (chartEl.value) {
    resizeObserver = new ResizeObserver(() => chart?.resize())
    resizeObserver.observe(chartEl.value)
  }
})
watch(() => props.overview, async (value) => {
  if (!value) return
  await nextTick()
  chart?.dispose()
  chart = null
  await draw()
})
watch(chartMetric, draw)
onBeforeUnmount(() => { resizeObserver?.disconnect(); chart?.dispose() })
</script>

<template>
  <div class="view-stack">
    <section class="page-intro"><span class="eyebrow">Last 60 days</span><h1>Study trends</h1><p>Completed duration and first session start time by day.</p></section>
    <section class="panel chart-panel"><div class="chart-toolbar"><div class="segmented-control" aria-label="Chart metric"><button :class="{ active: chartMetric === 'duration' }" @click="chartMetric = 'duration'">Duration</button><button :class="{ active: chartMetric === 'start' }" @click="chartMetric = 'start'">First start</button></div><b>Daily · 60d</b></div><div ref="chartEl" class="trend-chart" /></section>
    <section class="insight-grid panel" v-if="overview">
      <article class="insight"><span>Average first start</span><strong>{{ overview.summary.average_start_time || '--' }}</strong><p>Active days only</p></article>
      <article class="insight goal"><span>5H target days</span><strong>{{ overview.summary.five_hour_days }}</strong><p>{{ overview.summary.current_five_hour_streak }}-day current streak</p></article>
      <article class="insight"><span>Total completed</span><strong>{{ Math.floor(overview.summary.total_minutes / 60) }}h</strong><p>{{ overview.summary.session_count }} sessions</p></article>
    </section>
    <section v-if="overview" class="subject-time-grid panel" aria-label="Study time by subject">
      <header class="subject-time-heading"><div><span class="eyebrow">Subjects</span><h2>Study distribution</h2></div><span>Last {{ overview.range_days }} days</span></header>
      <article v-for="item in trackedSubjectStats" :key="item.subject" class="subject-time-card" :class="`subject-time-${item.subject}`">
        <header><span>{{ item.label }}</span><i /></header>
        <strong>{{ item.duration }}</strong>
        <footer><span>{{ item.share }}% of total</span><i :style="{ width: `${item.share}%` }" /></footer>
      </article>
    </section>
    <section v-if="overview" class="aggregate-grid">
      <article class="panel aggregate-card"><span class="eyebrow">WEEKLY BREAKDOWN</span><h2>Recent weeks</h2><div v-for="row in overview.weekly_totals.slice(-6).reverse()" :key="row.week_start"><span>{{ row.week_start }}</span><b>{{ Math.floor(row.minutes / 60) }}h {{ row.minutes % 60 }}m</b></div></article>
      <article class="panel aggregate-card"><span class="eyebrow">MONTHLY BREAKDOWN</span><h2>Recent months</h2><div v-for="row in overview.monthly_totals.slice(-6).reverse()" :key="row.month"><span>{{ row.month }}</span><b>{{ Math.floor(row.minutes / 60) }}h {{ row.minutes % 60 }}m</b></div></article>
      <article class="panel aggregate-card tag-stat-list"><span class="eyebrow">TAG BREAKDOWN</span><h2>Reusable content tags</h2><div v-for="row in overview.tag_totals.slice(0, 10)" :key="row.id"><span>#{{ row.name }}</span><small>{{ row.sessions }} sessions</small><b>{{ Math.floor(row.minutes / 60) }}h {{ row.minutes % 60 }}m</b></div><p v-if="!overview.tag_totals.length" class="section-note">No tagged Sessions yet.</p></article>
      <article class="panel aggregate-card tag-stat-list"><span class="eyebrow">TASK BREAKDOWN</span><h2>Preset paths</h2><div v-for="row in overview.task_totals.slice(0, 10)" :key="`${row.subject}:${row.path}`"><span>{{ row.subject_label }} · {{ row.path }}</span><small>{{ row.sessions }} sessions</small><b>{{ Math.floor(row.minutes / 60) }}h {{ row.minutes % 60 }}m</b></div><p v-if="!overview.task_totals.length" class="section-note">No preset Sessions yet.</p></article>
    </section>
  </div>
</template>
