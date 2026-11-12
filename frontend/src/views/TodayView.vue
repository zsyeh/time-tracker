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
const dailyTargetMinutes = computed(() => props.overview?.daily_target.minutes || 480)
const dailyTargetHours = computed(() => props.overview?.daily_target.hours || 8)
const mathMinutes = computed(() => props.overview?.today_subject_totals.find((item) => item.subject === 'math')?.minutes || 0)
const mathTargetMinutes = computed(() => props.overview?.subject_targets.math.minutes || 240)
const mathTargetHours = computed(() => props.overview?.subject_targets.math.hours || 4)
const mathHours = computed(() => `${Math.floor(mathMinutes.value / 60)}h ${mathMinutes.value % 60}m`)
const mathProgress = computed(() => Math.min(100, Math.round(mathMinutes.value / mathTargetMinutes.value * 100)))
const todayHours = computed(() => `${Math.floor(todayMinutes.value / 60)}h ${todayMinutes.value % 60}m`)
const todayProgress = computed(() => Math.min(100, Math.round(todayMinutes.value / dailyTargetMinutes.value * 100)))
const targetRemaining = computed(() => {
  const minutes = Math.max(0, dailyTargetMinutes.value - todayMinutes.value)
  return minutes ? t('remaining', { value: `${Math.floor(minutes / 60)}h ${minutes % 60}m` }) : t('complete')
})
const maxTodaySubject = computed(() => Math.max(1, ...(props.overview?.today_subject_totals.map((item) => item.minutes) || [])))
const todayLabel = computed(() => props.overview?.calendar.today
  ? new Intl.DateTimeFormat(language.value, { month: 'short', day: 'numeric', timeZone: 'Asia/Shanghai' }).format(new Date(`${props.overview.calendar.today}T12:00:00+08:00`))
  : t('today'))
const examDateLabel = computed(() => props.overview?.calendar.exam_date
  ? new Intl.DateTimeFormat(language.value, { year: 'numeric', month: 'short', day: 'numeric', timeZone: 'Asia/Shanghai' }).format(new Date(`${props.overview.calendar.exam_date}T12:00:00+08:00`))
  : '')

function scrollToSession() {
  document.getElementById('session-control')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}
</script>

<template>
  <div class="today-view">
    <PageHeader :context="t('workspace')" :title="t('today')" :metadata="todayLabel">
      <template #actions><button type="button" class="header-action" @click="scrollToSession">{{ overview?.active_session ? t('viewSession') : t('startSession') }}</button></template>
    </PageHeader>
    <div v-if="overview" class="today-countdown-strip" aria-label="Exam countdown">
      <div><span>{{ overview.private_display.countdown_label }}</span><time :datetime="overview.calendar.exam_date">{{ examDateLabel }}</time></div>
      <p><strong>{{ overview.calendar.days_until_exam }}</strong><span>{{ t('days') }}</span></p>
    </div>
    <div v-if="overview?.private_display.homepage_content || overview?.private_display.study_room_code" class="today-private-note">
      <span v-if="overview.private_display.homepage_content">{{ overview.private_display.homepage_content }}</span>
      <span v-if="overview.private_display.study_room_code">{{ t('studyRoom') }} · <b>{{ overview.private_display.study_room_code }}</b></span>
    </div>

    <section v-if="overview" class="today-section daily-progress-section" aria-labelledby="daily-progress-title">
      <header class="section-toolbar"><div><h2 id="daily-progress-title">{{ t('dailyProgress') }}</h2><span>{{ t('completedOnly') }}</span></div><span>{{ targetRemaining }}</span></header>
      <div class="today-overview-grid">
        <div class="daily-progress-block"><div class="daily-progress-main"><div><strong>{{ todayHours }}</strong><span>/ {{ dailyTargetHours }}h</span></div><b>{{ todayProgress }}%</b></div><div class="daily-progress-track" role="progressbar" :aria-label="`${dailyTargetHours} hour study target`" aria-valuemin="0" aria-valuemax="100" :aria-valuenow="todayProgress"><i :style="{ width: `${todayProgress}%` }" /></div><p>{{ todayProgress >= 100 ? t('targetComplete') : t('toTarget', { value: targetRemaining }) }}</p><div class="math-target-progress"><div><span>{{ t('mathDailyMinimum') }}</span><b>{{ mathHours }} / ≥{{ mathTargetHours }}h</b></div><div class="daily-progress-track subject-math" role="progressbar" :aria-label="`${mathTargetHours} hour mathematics target`" aria-valuemin="0" aria-valuemax="100" :aria-valuenow="mathProgress"><i :style="{ width: `${mathProgress}%` }" /></div></div></div>
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


<style scoped>
.today-countdown-strip { min-height: 54px; padding: 8px 2px; border-bottom: 1px solid var(--border-subtle); display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.today-countdown-strip > div { min-width: 0; display: flex; align-items: baseline; gap: 8px; }
.today-countdown-strip > div span { overflow: hidden; color: var(--text-secondary); font-size: 14px; font-weight: 550; text-overflow: ellipsis; white-space: nowrap; }
.today-countdown-strip time { color: var(--text-tertiary); font-size: 12px; white-space: nowrap; }
.today-countdown-strip p { margin: 0; flex: none; display: flex; align-items: baseline; gap: 5px; color: var(--text-tertiary); font-size: 12px; }
.today-countdown-strip strong { color: var(--text-primary); font-size: 32px; line-height: 1; font-variant-numeric: tabular-nums; font-weight: 650; letter-spacing: -.045em; }
.today-private-note { min-height: 31px; padding: 7px 2px; border-bottom: 1px solid var(--border-subtle); color: var(--text-tertiary); display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: 12px; }
.today-private-note b { color: var(--text-secondary); font-weight: 550; }
.today-section { padding: 20px 2px 22px; border-bottom: 1px solid var(--border-subtle); }
.today-section:last-child { border-bottom: 0; }
.today-overview-grid { border: 0; border-radius: 0; background: transparent; display: grid; grid-template-columns: minmax(0, 1.3fr) minmax(0, 1fr); overflow: visible; }
.daily-progress-block { min-width: 0; padding: 18px 20px; }
.daily-progress-main { margin-top: 3px; display: flex; align-items: baseline; justify-content: space-between; }
.daily-progress-main > div { display: flex; align-items: baseline; gap: 7px; }
.daily-progress-main strong { font: 600 29px/1.2 ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: -.04em; }
.daily-progress-main span, .daily-progress-main b { color: var(--text-tertiary); font-size: 12px; font-weight: 500; }
.daily-progress-track { height: 4px; margin-top: 11px; overflow: hidden; border-radius: 2px; background: var(--border-subtle); }
.daily-progress-track i { height: 100%; border-radius: inherit; background: var(--accent); display: block; }
.daily-progress-block > p { margin: 9px 0 0; color: var(--text-tertiary); font-size: 12px; }
.math-target-progress { margin-top: 16px; padding-top: 13px; border-top: 1px solid var(--border-subtle); }
.math-target-progress > div:first-child { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.math-target-progress span { color: var(--text-secondary); font-size: 14px; font-weight: 550; }
.math-target-progress b { color: var(--text-tertiary); font: 500 12px ui-monospace, SFMono-Regular, Menlo, monospace; white-space: nowrap; }
.math-target-progress .daily-progress-track { margin-top: 8px; }
.math-target-progress .daily-progress-track i { background: var(--subject-math); }
.overview-secondary { border-left: 0; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); }
.overview-secondary article { min-width: 0; padding: 16px 12px; border-left: 0; }
.overview-secondary article:first-child { border-left: 0; }
.overview-secondary span, .overview-secondary strong, .overview-secondary small { display: block; }
.overview-secondary span, .overview-secondary small { color: var(--text-secondary); font-size: 12px; white-space: normal; overflow-wrap: anywhere; }
.overview-secondary strong { margin: 9px 0 5px; font: 600 26px var(--font-ui); font-variant-numeric:tabular-nums; }
.daily-stat-columns { margin: 20px 0 0; display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); }
.daily-stat-columns > div { min-width: 0; padding: 0 16px; border-left: 1px solid var(--border-subtle); }
.daily-stat-columns > div:first-child { padding-left: 0; border-left: 0; }
.daily-stat-columns dt { color: var(--text-tertiary); font-size: 12px; }
.daily-stat-columns dd { margin: 4px 0 0; font: 550 13px ui-monospace, SFMono-Regular, Menlo, monospace; }
.today-subject-list { display: grid; }
.today-subject-list article { min-height: 48px; border-top: 1px solid var(--border-subtle); display: grid; grid-template-columns: 8px minmax(0, .7fr) 54px minmax(0, 1fr); align-items: center; gap: 10px; }
.today-subject-list article:first-child { border-top: 0; }
.today-subject-list strong { font-size: 14px; font-weight: 550; }
.today-subject-list > article > span { color: var(--text-tertiary); font: 12px ui-monospace, SFMono-Regular, Menlo, monospace; text-align: right; }
.today-subject-list > article > div { height: 3px; overflow: hidden; background: var(--border-subtle); }
.today-subject-list > article > div i { height: 100%; background: var(--subject); display: block; }
.today-subject-list .subject-math { --subject: var(--subject-math); }
.today-subject-list .subject-english { --subject: var(--subject-english); }
.today-subject-list .subject-major { --subject: var(--subject-major); }
.today-subject-list .subject-training { --subject: var(--subject-training); }
@media (max-width: 1024px) {
.today-overview-grid { grid-template-columns: 1fr; }
.overview-secondary { border-top: 1px solid var(--border-subtle); border-left: 0; }
}
@media (max-width: 768px) {
.daily-stat-columns { grid-template-columns: 1fr 1fr; gap: 14px 0; }
.daily-stat-columns > div:nth-child(3) { padding-left: 0; border-left: 0; }
}
@media (max-width: 520px) {
.today-countdown-strip > div { align-items: flex-start; flex-direction: column; gap: 1px; }
.today-countdown-strip strong { font-size: 29px; }
.overview-secondary { grid-template-columns: 1fr 1fr; }
.overview-secondary article:nth-child(3) { grid-column: 1/-1; border-top: 1px solid var(--border-subtle); border-left: 0; }
}
.today-view { min-width:0; } .daily-progress-block { padding-left:0; } .daily-progress-main { gap:12px; flex-wrap:wrap; } .daily-stat-columns { gap:16px; } .daily-stat-columns > div { padding:0; border:0; } @media(max-width:520px) { .daily-stat-columns { grid-template-columns:repeat(2,minmax(0,1fr)); } }
</style>
