<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { EChartsType } from '../lib/charts'
import { buildSubjectTimeStats } from '../lib/subjectStats'
import type { Overview } from '../types'
import { historicalHeatmapWindow } from '../lib/heatmap'
import PageHeader from '../components/layout/PageHeader.vue'
import { useUiPreferences } from '../lib/uiPreferences'
import { chartPalette, chartVisuals, onChartAppearanceChanged } from '../../shared/design/chartTheme'

const props = defineProps<{ overview: Overview | null }>()
const { language, scheme, t } = useUiPreferences()
const chartEl = ref<HTMLElement | null>(null)
const chartMetric = ref<'duration' | 'start'>('duration')
const rangeDays = ref<7 | 30 | 60 | 180>(60)
const trackedSubjectStats = computed(() => buildSubjectTimeStats(props.overview))
let chart: EChartsType | null = null
let resizeObserver: ResizeObserver | null = null
let stopAppearance: (()=>void) | undefined
let mounted = false
let drawSequence = 0
let resizeFrame = 0
const recentRows = computed(() => props.overview ? historicalHeatmapWindow(props.overview.heatmap, props.overview.calendar.today, rangeDays.value) : [])

function minuteToTime(value: number) {
  const normalized = Math.max(0, Math.min(1439, value))
  return `${Math.floor(normalized / 60).toString().padStart(2, '0')}:${Math.round(normalized % 60).toString().padStart(2, '0')}`
}

async function draw() {
  if (!chartEl.value || !props.overview) return
  const sequence = ++drawSequence
  const echarts = await import('../lib/charts')
  if (!mounted || sequence !== drawSequence || !chartEl.value) return
  if (!chart) chart = echarts.init(chartEl.value, undefined, { renderer: 'canvas' })
  // The dashboard heatmap intentionally extends through exam day so Today can
  // render future cells. Trends must anchor its windows to today; slicing the
  // raw array would otherwise select only future zero-value cells for 7D/30D.
  const recent = recentRows.value
  const starts = recent.map((row) => row.first_start ? Number(row.first_start.slice(0, 2)) * 60 + Number(row.first_start.slice(3, 5)) : null)
  const palette = chartPalette()
  const { accent, border, surface, primary: primaryText, text: tertiary } = palette
  const secondary = palette.comparison
  const showDuration = chartMetric.value === 'duration'
  const xAxisInterval = recent.length <= 7 ? 0 : Math.max(0, Math.ceil(recent.length / 7) - 1)
  chart.setOption({
    ...chartVisuals(palette),
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', confine: true, backgroundColor: surface, borderColor: border, padding: 10, textStyle: { color: primaryText, fontSize: 14 }, formatter(params: Array<{ axisValue: string; seriesName: string; value: number | null; marker: string }>) { return `${params[0]?.axisValue}<br/>${params.map((p) => `${p.marker}${p.seriesName}: ${!showDuration && p.value != null ? minuteToTime(p.value) : `${p.value || 0} min`}`).join('<br/>')}` } },
    grid: { left: 52, right: showDuration ? 22 : 58, top: 24, bottom: 38, containLabel: false },
    xAxis: { type: 'category', boundaryGap: showDuration, data: recent.map((r) => r.date.slice(5)), axisLabel: { color: tertiary, interval: xAxisInterval, hideOverlap: true, margin: 13, fontSize: 12 }, axisTick: { show: false }, axisLine: { lineStyle: { color: border } } },
    yAxis: [
      { show: showDuration, type: 'value', splitNumber: 5, axisLabel: { color: tertiary, fontSize: 12, formatter: (v: number) => v >= 60 ? `${Math.round(v / 60)}h` : `${v}m` }, axisTick: { show: false }, axisLine: { show: false }, splitLine: { lineStyle: { color: border, opacity: 0.7 } } },
      { show: !showDuration, type: 'value', min: 300, max: 900, inverse: true, interval: 120, axisLabel: { color: tertiary, fontSize: 12, formatter: (v: number) => minuteToTime(v) }, axisTick: { show: false }, axisLine: { show: false }, splitLine: { lineStyle: { color: border, opacity: 0.7 } } },
    ],
    series: showDuration
      ? [{ name: t('duration'), type: 'bar', data: recent.map((r) => r.minutes), barMaxWidth: 10, itemStyle: { color: (p: { data: number }) => p.data >= 300 ? accent : secondary, borderRadius: [2, 2, 0, 0] }, markLine: { silent: true, symbol: 'none', label: { color: tertiary, formatter: '5h' }, lineStyle: { color: accent, type: 'dashed', opacity: 0.35 }, data: [{ yAxis: 300 }] } }]
      : [{ name: t('firstStart'), type: 'line', yAxisIndex: 1, data: starts, connectNulls: false, showSymbol: false, smooth: 0.18, lineStyle: { color: accent, width: 2 }, itemStyle: { color: accent } }],
  }, true)
}

function resizeChart() {
  if (resizeFrame) cancelAnimationFrame(resizeFrame)
  resizeFrame = requestAnimationFrame(() => { if (mounted) chart?.resize() })
}
function visibilityChanged() { if (document.visibilityState === 'visible') resizeChart() }
onMounted(async () => {
  mounted = true
  stopAppearance = onChartAppearanceChanged(() => { void draw() })
  window.addEventListener('resize', resizeChart)
  window.addEventListener('orientationchange', resizeChart)
  window.addEventListener('pageshow', resizeChart)
  window.visualViewport?.addEventListener('resize', resizeChart)
  document.addEventListener('visibilitychange', visibilityChanged)
  await nextTick()
  await draw()
  if (chartEl.value) {
    resizeObserver = new ResizeObserver(resizeChart)
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
watch([chartMetric, rangeDays, language, scheme], draw)
onBeforeUnmount(() => { mounted = false; drawSequence += 1; stopAppearance?.(); cancelAnimationFrame(resizeFrame); resizeObserver?.disconnect(); chart?.dispose(); window.removeEventListener('resize', resizeChart); window.removeEventListener('orientationchange', resizeChart); window.removeEventListener('pageshow', resizeChart); window.visualViewport?.removeEventListener('resize', resizeChart); document.removeEventListener('visibilitychange', visibilityChanged) })
</script>

<template>
  <div class="view-stack trends-page">
    <PageHeader :context="t('workspace')" :title="t('trends')" :metadata="t('lastDays', { days: rangeDays })">
      <template #actions><div class="header-segmented" aria-label="Trend range"><button v-for="days in ([7, 30, 60, 180] as const)" :key="days" :class="{ active: rangeDays === days }" @click="rangeDays = days">{{ days }}D</button></div></template>
    </PageHeader>
    <div class="trend-analytics-grid">
      <section class="panel chart-panel"><div class="chart-toolbar"><div class="segmented-control" aria-label="Chart metric"><button :class="{ active: chartMetric === 'duration' }" @click="chartMetric = 'duration'">{{ t('duration') }}</button><button :class="{ active: chartMetric === 'start' }" @click="chartMetric = 'start'">{{ t('firstStart') }}</button></div><b>{{ t('daily') }} · {{ t('lastDays', { days: rangeDays }) }}</b></div><div ref="chartEl" class="trend-chart" role="img" :aria-label="`${t('daily')} · ${t('lastDays', { days: rangeDays })}`" /><details class="chart-data"><summary>View chart data</summary><div class="chart-data-scroll"><table><caption>Daily study data</caption><thead><tr><th scope="col">Date</th><th scope="col">Minutes</th><th scope="col">First start</th></tr></thead><tbody><tr v-for="row in recentRows" :key="row.date"><th scope="row">{{ row.date }}</th><td>{{ row.minutes }}</td><td>{{ row.first_start || '—' }}</td></tr></tbody></table></div></details></section>
      <aside v-if="overview" class="trend-summary" aria-label="Trend summary">
        <header><span>{{ t('overview') }}</span><b>{{ rangeDays }}D</b></header>
        <article class="insight"><span>{{ t('averageFirstStart') }}</span><strong>{{ overview.summary.average_start_time || '--' }}</strong><p>{{ t('activeDaysOnly') }}</p></article>
        <article class="insight goal"><span>{{ t('targetDays') }}</span><strong>{{ overview.summary.five_hour_days }}</strong><p>{{ t('currentStreakLabel', { days: overview.summary.current_five_hour_streak }) }}</p></article>
        <article class="insight"><span>{{ t('totalCompleted') }}</span><strong>{{ Math.floor(overview.summary.total_minutes / 60) }}h</strong><p>{{ overview.summary.session_count }} {{ t('sessions').toLocaleLowerCase() }}</p></article>
      </aside>
    </div>
    <section v-if="overview" class="trend-section subject-time-grid" aria-label="Study time by subject">
      <header class="subject-time-heading"><div><span class="eyebrow">{{ t('subjects') }}</span><h2>{{ t('studyDistribution') }}</h2></div><span>{{ t('lastDays', { days: overview.range_days }) }}</span></header>
      <article v-for="item in trackedSubjectStats" :key="item.subject" class="subject-time-card" :class="`subject-time-${item.subject}`">
        <header><span>{{ item.label }}</span><i /></header>
        <strong>{{ item.duration }}</strong>
        <footer><span>{{ item.share }}% {{ t('ofTotal') }}</span><i :style="{ width: `${item.share}%` }" /></footer>
      </article>
    </section>
    <section v-if="overview" class="trend-breakdowns">
      <article class="trend-data-group"><header><h2>{{ t('recentWeeks') }}</h2><span>6 {{ t('weeks') }}</span></header><div class="trend-data-row" v-for="row in overview.weekly_totals.slice(-6).reverse()" :key="row.week_start"><span>{{ row.week_start }}</span><b>{{ Math.floor(row.minutes / 60) }}h {{ row.minutes % 60 }}m</b></div></article>
      <article class="trend-data-group"><header><h2>{{ t('recentMonths') }}</h2><span>6 {{ t('months') }}</span></header><div class="trend-data-row" v-for="row in overview.monthly_totals.slice(-6).reverse()" :key="row.month"><span>{{ row.month }}</span><b>{{ Math.floor(row.minutes / 60) }}h {{ row.minutes % 60 }}m</b></div></article>
      <article class="trend-data-group"><header><h2>Tags</h2><span>Reusable labels</span></header><div class="trend-data-row has-meta" v-for="row in overview.tag_totals.slice(0, 10)" :key="row.id"><span>#{{ row.name }}<small>{{ row.sessions }} sessions</small></span><b>{{ Math.floor(row.minutes / 60) }}h {{ row.minutes % 60 }}m</b></div><p v-if="!overview.tag_totals.length" class="section-note">No tagged Sessions yet.</p></article>
      <article class="trend-data-group"><header><h2>Tasks</h2><span>Preset paths</span></header><div class="trend-data-row has-meta" v-for="row in overview.task_totals.slice(0, 10)" :key="`${row.subject}:${row.path}`"><span>{{ row.subject_label }} · {{ row.path }}<small>{{ row.sessions }} sessions</small></span><b>{{ Math.floor(row.minutes / 60) }}h {{ row.minutes % 60 }}m</b></div><p v-if="!overview.task_totals.length" class="section-note">No preset Sessions yet.</p></article>
    </section>
  </div>
</template>

<style scoped>
.trends-page { min-width:0; } .trend-analytics-grid { display:grid; grid-template-columns:minmax(0,1fr); gap:24px; }
.chart-panel { padding:0; border:0; border-radius:0; background:transparent; box-shadow:none; } .chart-toolbar { display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:12px; padding:0; } .chart-toolbar > b { font-size:13px; font-weight:500; color:var(--text-secondary); }
.trend-chart { width:100%; min-width:0; height:360px; } .trend-summary { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:16px; padding:16px 0; border:0; border-block:1px solid var(--border-subtle); background:transparent; }
.trend-summary > header { grid-column:1/-1; display:flex; align-items:center; justify-content:space-between; gap:12px; min-height:32px; padding:0; border:0; color:var(--text-secondary); font-size:13px; } .trend-summary > header b { font-size:12px; }
.insight { min-width:0; padding:8px 0; border:0; } .insight span,.insight p { font-size:13px; line-height:1.5; color:var(--text-secondary); } .insight p { margin:0; } .insight > span, .insight > strong { display:block; } .insight strong { line-height:1.2; font-family:inherit; font-variant-numeric:tabular-nums; font-size:28px; margin:8px 0; }
.subject-time-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:16px; padding:0 0 24px; } .subject-time-heading { grid-column:1/-1; display:flex; gap:12px; justify-content:space-between; padding:12px 0; border:0; } .subject-time-heading h2 { margin:0; font-size:17px; } .subject-time-heading > span { font-size:12px; } .subject-time-heading .eyebrow { display:none; }
.subject-time-card { min-width:0; padding:8px 0; border:0; } .subject-time-card header { display:flex; align-items:center; justify-content:space-between; gap:8px; font-size:14px; } .subject-time-card header i { width:6px; height:6px; flex:none; border-radius:50%; background:var(--subject); } .subject-time-card > strong { font-size:28px; font-family:inherit; font-variant-numeric:tabular-nums; } .subject-time-card footer { display:grid; grid-template-columns:auto minmax(0,1fr); align-items:center; gap:8px; color:var(--text-secondary); font-size:12px; } .subject-time-card footer::before { content:""; grid-column:2; grid-row:1; height:3px; background:var(--border-subtle); } .subject-time-card footer i { display:block; grid-column:2; grid-row:1; height:3px; max-width:100%; background:var(--subject); } .subject-time-math { --subject:var(--subject-math); } .subject-time-english { --subject:var(--subject-english); } .subject-time-major { --subject:var(--subject-major); }
.trend-breakdowns { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:24px; } .trend-data-group { min-width:0; padding:16px 0; border:0; border-top:1px solid var(--border-subtle); border-radius:0; background:transparent; } .trend-data-group > header { display:flex; align-items:baseline; justify-content:space-between; gap:12px; min-height:34px; } .trend-data-group h2 { margin:0; font-size:17px; } .trend-data-group header span { font-size:12px; } .trend-data-row { display:grid; grid-template-columns:minmax(0,1fr) auto; align-items:center; gap:16px; min-height:48px; padding:8px 0; border-top:1px solid var(--border-subtle); color:var(--text-secondary); font-size:14px; line-height:1.5; } .trend-data-row > span { min-width:0; overflow-wrap:anywhere; } .trend-data-row small { display:block; margin-top:4px; color:var(--text-secondary); font-size:12px; } .trend-data-row b { color:var(--text-primary); white-space:nowrap; font:500 14px var(--font-ui); font-variant-numeric:tabular-nums; }
.chart-data { color:var(--text-secondary); font-size:13px; } .chart-data summary { min-height:44px; display:flex; align-items:center; cursor:pointer; } .chart-data-scroll { overflow:auto; max-width:100%; } table { border-collapse:collapse; width:100%; font-size:13px; font-variant-numeric:tabular-nums; } caption { text-align:left; padding:8px 0; } th,td { border-bottom:1px solid var(--border-subtle); padding:8px; text-align:right; } th:first-child { text-align:left; }
@media(max-width:700px) { .trend-summary { grid-template-columns:minmax(0,1fr); gap:8px; } .insight { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:4px 12px; align-items:baseline; } .insight p { grid-column:1/-1; } .insight strong { font-size:26px; margin:0; } .subject-time-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } .trend-breakdowns { grid-template-columns:minmax(0,1fr); } .trend-chart { height:300px; } }
</style>
