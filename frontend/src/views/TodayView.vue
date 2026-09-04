<script setup lang="ts">
import { computed } from 'vue'
import ActiveSession from '../components/ActiveSession.vue'
import HeatmapGrid from '../components/HeatmapGrid.vue'
import PageHeader from '../components/layout/PageHeader.vue'
import type { Overview } from '../types'
import { useUiPreferences } from '../lib/uiPreferences'

const props = defineProps<{ overview: Overview | null }>()
const emit = defineEmits<{ changed: [] }>()

const { language, t } = useUiPreferences()
const subjectLabels = computed<Record<string, string>>(() => ({ math: t('mathematics'), english: t('english'), major: t('major'), training: t('training') }))
const todayMinutes = computed(() => props.overview?.today.minutes || 0)
const todayHours = computed(() => `${Math.floor(todayMinutes.value / 60)}h ${todayMinutes.value % 60}m`)
const todayProgress = computed(() => Math.min(100, Math.round(todayMinutes.value / 300 * 100)))
const targetRemaining = computed(() => {
  const minutes = Math.max(0, 300 - todayMinutes.value)
  return minutes ? t('remaining', { value: `${Math.floor(minutes / 60)}h ${minutes % 60}m` }) : t('complete')
})
const maxTodaySubject = computed(() => Math.max(1, ...(props.overview?.today_subject_totals.map((item) => item.minutes) || [])))
const todayLabel = computed(() => props.overview?.calendar.today
  ? new Intl.DateTimeFormat(language.value, { month: 'short', day: 'numeric', timeZone: 'Asia/Shanghai' }).format(new Date(`${props.overview.calendar.today}T12:00:00+08:00`))
  : t('today'))
const headerMetadata = computed(() => {
  const days = props.overview?.calendar.days_until_exam
  return `${todayLabel.value}${days === undefined ? '' : ` · ${t('examIn', { days })}`}`
})

function scrollToSession() {
  document.getElementById('session-control')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}
</script>

<template>
  <div class="today-view">
    <PageHeader :context="t('workspace')" :title="t('today')" :metadata="headerMetadata">
      <template #actions><button type="button" class="header-action" @click="scrollToSession">{{ overview?.active_session ? t('viewSession') : t('startSession') }}</button></template>
    </PageHeader>
    <div v-if="overview?.private_display.homepage_content || overview?.private_display.study_room_code" class="today-private-note">
      <span v-if="overview.private_display.homepage_content">{{ overview.private_display.homepage_content }}</span>
      <span v-if="overview.private_display.study_room_code">{{ t('studyRoom') }} · <b>{{ overview.private_display.study_room_code }}</b></span>
    </div>

    <section v-if="overview" class="today-section daily-progress-section" aria-labelledby="daily-progress-title">
      <header class="section-toolbar"><div><h2 id="daily-progress-title">{{ t('dailyProgress') }}</h2><span>{{ t('completedOnly') }}</span></div><span>{{ targetRemaining }}</span></header>
      <div class="today-overview-grid">
        <div class="daily-progress-block"><div class="daily-progress-main"><div><strong>{{ todayHours }}</strong><span>/ 5h</span></div><b>{{ todayProgress }}%</b></div><div class="daily-progress-track" role="progressbar" aria-label="Five hour study target" aria-valuemin="0" aria-valuemax="100" :aria-valuenow="todayProgress"><i :style="{ width: `${todayProgress}%` }" /></div><p>{{ todayProgress >= 100 ? t('targetComplete') : t('toTarget', { value: targetRemaining }) }}</p></div>
        <div class="overview-secondary"><article><span>{{ t('activeDays') }}</span><strong>{{ overview.summary.active_days }}</strong><small>{{ t('lastDays', { days: overview.range_days }) }}</small></article><article><span>{{ t('fiveHourDays') }}</span><strong>{{ overview.summary.five_hour_days }}</strong><small>{{ t('bestStreak', { days: overview.summary.longest_five_hour_streak }) }}</small></article><article><span>{{ t('total') }}</span><strong>{{ Math.floor(overview.summary.total_minutes / 60) }}h</strong><small>{{ overview.summary.session_count }} {{ t('sessions').toLocaleLowerCase() }}</small></article></div>
      </div>
      <dl class="daily-stat-columns">
        <div><dt>{{ t('firstStart') }}</dt><dd>{{ overview.today.first_start || '—' }}</dd></div>
        <div><dt>{{ t('sessions') }}</dt><dd>{{ overview.today.sessions }}</dd></div>
        <div><dt>{{ t('currentStreak') }}</dt><dd>{{ overview.summary.current_streak }} {{ t('days') }}</dd></div>
        <div><dt>{{ t('fiveHourStreak') }}</dt><dd>{{ overview.summary.current_five_hour_streak }} {{ t('days') }}</dd></div>
      </dl>
    </section>

    <section id="session-control" class="today-section session-control-section" aria-labelledby="session-control-title">
      <header class="section-toolbar"><div><h2 id="session-control-title">{{ t('session') }}</h2><span>{{ overview?.active_session ? t('inProgress') : t('chooseTask') }}</span></div></header>
      <ActiveSession :session="overview?.active_session || null" :shortcuts="overview?.task_shortcuts || []" @changed="emit('changed')" />
    </section>

    <section v-if="overview" class="today-section today-subject-section" aria-labelledby="today-subject-title">
      <header class="section-toolbar"><div><h2 id="today-subject-title">{{ t('subjects') }}</h2><span>{{ t('today') }}</span></div><span>{{ todayHours }} {{ t('total').toLocaleLowerCase() }}</span></header>
      <div class="today-subject-list">
        <article v-for="item in overview.today_subject_totals" :key="item.subject" :class="`subject-${item.subject}`">
          <i class="subject-dot" /><strong>{{ subjectLabels[item.subject] }}</strong><span>{{ item.minutes }}m</span><div><i :style="{ width: `${item.minutes / maxTodaySubject * 100}%` }" /></div>
        </article>
      </div>
    </section>

    <section v-if="overview" class="today-section activity-section" aria-labelledby="activity-title">
      <header class="section-toolbar"><div><h2 id="activity-title">{{ t('activity') }}</h2><span>{{ t('consistency') }}</span></div><span>{{ t('lastDays', { days: overview.range_days }) }}</span></header>
      <HeatmapGrid :days="overview.heatmap" />
    </section>
  </div>
</template>
