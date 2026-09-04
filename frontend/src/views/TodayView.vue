<script setup lang="ts">
import { computed } from 'vue'
import ActiveSession from '../components/ActiveSession.vue'
import HeatmapGrid from '../components/HeatmapGrid.vue'
import PageHeader from '../components/layout/PageHeader.vue'
import type { Overview } from '../types'

const props = defineProps<{ overview: Overview | null }>()
const emit = defineEmits<{ changed: [] }>()

const subjectLabels: Record<string, string> = { math: 'Mathematics', english: 'English', major: 'Major / 892', training: 'Training' }
const todayMinutes = computed(() => props.overview?.today.minutes || 0)
const todayHours = computed(() => `${Math.floor(todayMinutes.value / 60)}h ${todayMinutes.value % 60}m`)
const todayProgress = computed(() => Math.min(100, Math.round(todayMinutes.value / 300 * 100)))
const targetRemaining = computed(() => {
  const minutes = Math.max(0, 300 - todayMinutes.value)
  return minutes ? `${Math.floor(minutes / 60)}h ${minutes % 60}m left` : 'Complete'
})
const maxTodaySubject = computed(() => Math.max(1, ...(props.overview?.today_subject_totals.map((item) => item.minutes) || [])))
const todayLabel = computed(() => props.overview?.calendar.today
  ? new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', timeZone: 'Asia/Shanghai' }).format(new Date(`${props.overview.calendar.today}T12:00:00+08:00`))
  : 'Today')
const headerMetadata = computed(() => {
  const days = props.overview?.calendar.days_until_exam
  return `${todayLabel.value}${days === undefined ? '' : ` · Exam in ${days} days`}`
})

function scrollToSession() {
  document.getElementById('session-control')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}
</script>

<template>
  <div class="today-view">
    <PageHeader title="Today" :metadata="headerMetadata">
      <template #actions><button type="button" class="header-action" @click="scrollToSession">{{ overview?.active_session ? 'View session' : 'Start session' }}</button></template>
    </PageHeader>
    <div v-if="overview?.private_display.homepage_content || overview?.private_display.study_room_code" class="today-private-note">
      <span v-if="overview.private_display.homepage_content">{{ overview.private_display.homepage_content }}</span>
      <span v-if="overview.private_display.study_room_code">Study room · <b>{{ overview.private_display.study_room_code }}</b></span>
    </div>

    <section v-if="overview" class="today-section daily-progress-section" aria-labelledby="daily-progress-title">
      <header class="section-toolbar"><div><h2 id="daily-progress-title">Daily progress</h2><span>Completed sessions only</span></div><span>{{ targetRemaining }}</span></header>
      <div class="daily-progress-main"><div><strong>{{ todayHours }}</strong><span>/ 5h</span></div><b>{{ todayProgress }}%</b></div>
      <div class="daily-progress-track" role="progressbar" aria-label="Five hour study target" aria-valuemin="0" aria-valuemax="100" :aria-valuenow="todayProgress"><i :style="{ width: `${todayProgress}%` }" /></div>
      <dl class="daily-stat-columns">
        <div><dt>First start</dt><dd>{{ overview.today.first_start || '—' }}</dd></div>
        <div><dt>Sessions</dt><dd>{{ overview.today.sessions }}</dd></div>
        <div><dt>Current streak</dt><dd>{{ overview.summary.current_streak }} days</dd></div>
        <div><dt>5H streak</dt><dd>{{ overview.summary.current_five_hour_streak }} days</dd></div>
      </dl>
    </section>

    <section id="session-control" class="today-section session-control-section" aria-labelledby="session-control-title">
      <header class="section-toolbar"><div><h2 id="session-control-title">Session</h2><span>{{ overview?.active_session ? 'In progress' : 'Choose a subject or saved task' }}</span></div></header>
      <ActiveSession :session="overview?.active_session || null" :shortcuts="overview?.task_shortcuts || []" @changed="emit('changed')" />
    </section>

    <section v-if="overview" class="today-section today-subject-section" aria-labelledby="today-subject-title">
      <header class="section-toolbar"><div><h2 id="today-subject-title">Subjects</h2><span>Today</span></div><span>{{ todayHours }} total</span></header>
      <div class="today-subject-list">
        <article v-for="item in overview.today_subject_totals" :key="item.subject" :class="`subject-${item.subject}`">
          <i class="subject-dot" /><strong>{{ subjectLabels[item.subject] }}</strong><span>{{ item.minutes }}m</span><div><i :style="{ width: `${item.minutes / maxTodaySubject * 100}%` }" /></div>
        </article>
      </div>
    </section>

    <section v-if="overview" class="today-section activity-section" aria-labelledby="activity-title">
      <header class="section-toolbar"><div><h2 id="activity-title">Activity</h2><span>Study consistency and daily drilldown</span></div><span>Last {{ overview.range_days }} days</span></header>
      <HeatmapGrid :days="overview.heatmap" />
    </section>
  </div>
</template>
