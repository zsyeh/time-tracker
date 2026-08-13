<script setup lang="ts">
import { computed } from 'vue'
import ActiveSession from '../components/ActiveSession.vue'
import HeatmapGrid from '../components/HeatmapGrid.vue'
import MetricCard from '../components/MetricCard.vue'
import { buildSubjectTimeStats } from '../lib/subjectStats'
import type { Overview } from '../types'

const props = defineProps<{ overview: Overview | null }>()
const emit = defineEmits<{ changed: [] }>()

const subjectLabels: Record<string, string> = { math: 'Mathematics', english: 'English', major: 'Major', training: 'Training' }
const todayHours = computed(() => props.overview ? `${Math.floor(props.overview.today.minutes / 60)}h ${props.overview.today.minutes % 60}m` : '--')
const trackedSubjectStats = computed(() => buildSubjectTimeStats(props.overview))
const maxTodaySubject = computed(() => Math.max(1, ...(props.overview?.today_subject_totals.map((item) => item.minutes) || [])))
const todayProgress = computed(() => Math.min(100, Math.round((props.overview?.today.minutes || 0) / 300 * 100)))
const statusLabel = computed(() => todayProgress.value >= 100 ? 'TARGET MET' : props.overview?.active_session ? 'SESSION ACTIVE' : 'NO ACTIVE SESSION')
const todayLabel = computed(() => props.overview?.calendar.today.replaceAll('-', '.') || '----.--.--')
const weekdayLabel = computed(() => {
  if (!props.overview) return 'TODAY'
  return new Intl.DateTimeFormat('en-US', { weekday: 'long', timeZone: 'Asia/Shanghai' })
    .format(new Date(`${props.overview.calendar.today}T12:00:00+08:00`)).toUpperCase()
})
</script>

<template>
  <div>
    <section class="hero exam-hero">
      <div class="date-block"><span class="eyebrow">TODAY / {{ weekdayLabel }}</span><h1>{{ todayLabel }}</h1><p>LOCAL DATE · ASIA/SHANGHAI</p><p v-if="overview?.private_display.homepage_content" class="homepage-content">{{ overview.private_display.homepage_content }}</p><p v-if="overview?.private_display.study_room_code" class="study-room-code">STUDY ROOM · {{ overview.private_display.study_room_code }}</p></div>
      <div class="exam-countdown"><span>{{ overview?.private_display.countdown_label || '2026 POSTGRADUATE EXAM' }}</span><div><b>{{ overview?.calendar.days_until_exam ?? '--' }}</b><small>DAYS</small></div><time>{{ overview?.calendar.exam_date || '2026-12-26' }}</time></div>
    </section>
    <ActiveSession :session="overview?.active_session || null" :shortcuts="overview?.task_shortcuts || []" @changed="emit('changed')" />
    <section v-if="overview" class="status-overview panel">
      <div class="status-ring" :style="{ '--status-progress': `${todayProgress * 3.6}deg` }"><div><strong>{{ todayProgress }}</strong><span>%</span><small>5H TARGET</small></div></div>
      <div class="status-copy"><span class="eyebrow">DAILY STATUS</span><h2>{{ statusLabel }}</h2><p>Completed sessions only. Active duration remains hidden.</p></div>
      <dl><div><dt>FIRST START</dt><dd>{{ overview.today.first_start || '--' }}</dd></div><div><dt>SESSIONS</dt><dd>{{ overview.today.sessions }}</dd></div><div><dt>DATE</dt><dd>{{ overview.calendar.today.slice(5) }}</dd></div></dl>
    </section>
    <section v-if="overview" class="metrics-grid">
      <MetricCard label="TODAY" :value="todayHours" :hint="`First start ${overview.today.first_start || '--'}`" tone="goal" />
      <MetricCard label="CURRENT STREAK" :value="overview.summary.current_streak" suffix="days" :hint="`Longest ${overview.summary.longest_streak} days`" />
      <MetricCard label="5H STREAK" :value="overview.summary.current_five_hour_streak" suffix="days" :hint="`Longest ${overview.summary.longest_five_hour_streak} days`" tone="goal" />
      <MetricCard label="5H DAYS" :value="overview.summary.five_hour_days" suffix="days" hint="Last 180 days" tone="warm" />
      <MetricCard label="AVG. START" :value="overview.summary.average_start_time || '--'" hint="First session per active day" tone="blue" />
      <MetricCard label="ACTIVE DAYS" :value="overview.summary.active_days" suffix="days" :hint="`${overview.summary.session_count} completed sessions`" />
    </section>
    <section v-if="overview" class="subject-time-grid" aria-label="Study time by subject">
      <article v-for="item in trackedSubjectStats" :key="item.subject" class="panel subject-time-card" :class="`subject-time-${item.subject}`">
        <header><span>{{ item.label }}</span><i /></header>
        <strong>{{ item.duration }}</strong>
        <footer><span>LAST {{ overview.range_days }} DAYS</span><b>{{ item.share }}% OF TOTAL</b></footer>
      </article>
    </section>
    <section v-if="overview" class="panel subject-strip">
      <div><span class="eyebrow">BREAKDOWN</span><h2>Today by subject</h2></div>
      <div class="subject-bars"><article v-for="item in overview.today_subject_totals" :key="item.subject"><span>{{ subjectLabels[item.subject] }}</span><div><i :class="`subject-${item.subject}`" :style="{ width: `${Math.max(item.minutes ? 5 : 0, item.minutes / maxTodaySubject * 100)}%` }" /></div><b>{{ item.minutes }}m</b></article></div>
    </section>
    <HeatmapGrid v-if="overview" :days="overview.heatmap" />
  </div>
</template>
