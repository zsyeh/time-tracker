<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
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
    tooltip: { trigger: 'axis', backgroundColor: '#10201a', borderColor: '#29463b', textStyle: { color: '#eaf4ef' }, formatter(params: Array<{ axisValue: string; seriesName: string; value: number | null; marker: string }>) { return `${params[0]?.axisValue}<br/>${params.map((p) => `${p.marker}${p.seriesName}：${p.seriesName === '开始时间' && p.value != null ? minuteToTime(p.value) : `${p.value || 0} 分钟`}`).join('<br/>')}` } },
    legend: { data: ['学习时长', '开始时间'], textStyle: { color: '#92aa9f' }, top: 0 },
    grid: { left: 45, right: 50, top: 45, bottom: 35 },
    xAxis: { type: 'category', data: recent.map((r) => r.date.slice(5)), axisLabel: { color: '#789086', interval: 6 }, axisLine: { lineStyle: { color: '#254036' } } },
    yAxis: [
      { type: 'value', name: '分钟', nameTextStyle: { color: '#789086' }, axisLabel: { color: '#789086' }, splitLine: { lineStyle: { color: '#183128' } } },
      { type: 'value', min: 300, max: 900, inverse: true, interval: 120, axisLabel: { color: '#789086', formatter: (v: number) => minuteToTime(v) }, splitLine: { show: false } },
    ],
    series: [
      { name: '学习时长', type: 'bar', data: recent.map((r) => r.minutes), barMaxWidth: 12, itemStyle: { color: (p: { data: number }) => p.data >= 300 ? '#dfff72' : '#2d8c70', borderRadius: [3, 3, 0, 0] }, markLine: { silent: true, symbol: 'none', label: { color: '#dfff72', formatter: '5h' }, lineStyle: { color: '#dfff72', type: 'dashed', opacity: 0.55 }, data: [{ yAxis: 300 }] } },
      { name: '开始时间', type: 'line', yAxisIndex: 1, data: starts, connectNulls: false, showSymbol: false, smooth: 0.25, lineStyle: { color: '#e8a84c', width: 2 }, itemStyle: { color: '#e8a84c' } },
    ],
  })
}

function resize() { chart?.resize() }
onMounted(async () => { await nextTick(); await draw(); window.addEventListener('resize', resize, { passive: true }) })
onBeforeUnmount(() => { window.removeEventListener('resize', resize); chart?.dispose() })
</script>

<template>
  <div class="view-stack">
    <section class="page-intro"><span class="eyebrow">TREND ANALYSIS</span><h1>学习趋势</h1><p>最近 60 天的投入时长和每日第一次开始学习时间。</p></section>
    <section class="panel chart-panel"><div ref="chartEl" class="trend-chart" /></section>
    <section class="insight-grid" v-if="overview">
      <article class="panel insight"><span>平均开始时间</span><strong>{{ overview.summary.average_start_time || '--' }}</strong><p>只统计有学习记录的日期</p></article>
      <article class="panel insight goal"><span>5 小时达标日</span><strong>{{ overview.summary.five_hour_days }}</strong><p>当前连续 {{ overview.summary.current_five_hour_streak }} 天</p></article>
      <article class="panel insight"><span>总投入</span><strong>{{ Math.floor(overview.summary.total_minutes / 60) }}h</strong><p>{{ overview.summary.session_count }} 个完成记录</p></article>
    </section>
    <section v-if="overview" class="aggregate-grid">
      <article class="panel aggregate-card"><span class="eyebrow">WEEKLY</span><h2>最近周投入</h2><div v-for="row in overview.weekly_totals.slice(-6).reverse()" :key="row.week_start"><span>{{ row.week_start }}</span><b>{{ Math.floor(row.minutes / 60) }}h {{ row.minutes % 60 }}m</b></div></article>
      <article class="panel aggregate-card"><span class="eyebrow">MONTHLY</span><h2>最近月投入</h2><div v-for="row in overview.monthly_totals.slice(-6).reverse()" :key="row.month"><span>{{ row.month }}</span><b>{{ Math.floor(row.minutes / 60) }}h {{ row.minutes % 60 }}m</b></div></article>
    </section>
  </div>
</template>
