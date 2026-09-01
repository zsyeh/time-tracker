<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { View } from '@element-plus/icons-vue'
import { api, post } from '../lib/api'
import { heatmapLevelClass } from '../lib/heatmap'
import type { HeatmapDay, Page, ReviewTrend as ReviewTrendType, StudySession, StudySessionSummary } from '../types'
import MarkdownPreview from './MarkdownPreview.vue'
import ReviewTrend from './ReviewTrend.vue'

const props = defineProps<{ days: HeatmapDay[] }>()
const router = useRouter()
const detailOpen = ref(false)
const sessionOpen = ref(false)
const sessionLoading = ref(false)
const loading = ref(false)
const selected = ref<HeatmapDay | null>(null)
const selectedSession = ref<StudySession | null>(null)
const selectedSessionTitle = ref('')
const reviewTrend = ref<ReviewTrendType | null>(null)
const sessions = ref<StudySessionSummary[]>([])

const cells = computed(() => {
  if (!props.days.length) return []
  const first = new Date(`${props.days[0].date}T00:00:00`).getDay()
  return [...Array.from({ length: first }, () => null), ...props.days]
})

function duration(minutes: number) {
  if (!minutes) return '0m'
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  return `${hours ? `${hours}h` : ''}${rest ? ` ${rest}m` : ''}`.trim()
}

function timelineStyle(session: StudySessionSummary) {
  const start = new Date(session.start_time)
  const end = new Date(session.end_time || session.start_time)
  const startMinutes = start.getHours() * 60 + start.getMinutes()
  const endMinutes = Math.min(1440, end.getHours() * 60 + end.getMinutes() + (end.getDate() !== start.getDate() ? 1440 : 0))
  return {
    left: `${(startMinutes / 1440) * 100}%`,
    width: `${Math.max(0.7, ((endMinutes - startMinutes) / 1440) * 100)}%`,
  }
}

async function openDay(day: HeatmapDay | null) {
  if (!day || day.is_future) return
  selected.value = day
  detailOpen.value = true
  loading.value = true
  try {
    const result = await api<Page<StudySessionSummary>>(`/api/sessions/?date_from=${day.date}&date_to=${day.date}`)
    sessions.value = result.results.filter((item) => item.status === 'completed')
  } catch (error) {
    ElMessage.error((error as Error).message)
  } finally {
    loading.value = false
  }
}

async function openSession(session: StudySessionSummary) {
  selectedSession.value = null
  selectedSessionTitle.value = session.title || 'Untitled session'
  reviewTrend.value = null
  sessionOpen.value = true
  sessionLoading.value = true
  try {
    const [detail, trend] = await Promise.all([
      api<StudySession>(`/api/sessions/${session.uuid}/`),
      post<ReviewTrendType>(`/api/sessions/${session.uuid}/reviews/`),
    ])
    detail.review_count = trend.total
    detail.last_reviewed_at = trend.last_reviewed_at
    session.review_count = trend.total
    session.last_reviewed_at = trend.last_reviewed_at
    selectedSession.value = detail
    reviewTrend.value = trend
  } catch (error) {
    ElMessage.error((error as Error).message)
  } finally {
    sessionLoading.value = false
  }
}
</script>

<template>
  <section class="panel heatmap-panel">
    <div class="section-heading">
      <div>
        <span class="eyebrow">ACTIVITY / DRILLDOWN</span>
        <h2>Study activity</h2>
      </div>
      <div class="legend" aria-label="Activity intensity legend">
        <span>LESS</span><i class="cell level-0" /><i class="cell level-1" /><i class="cell level-2" />
        <i class="cell level-4" /><span>≥5H</span><i class="cell level-8-plus" /><span>&gt;8H</span><i class="cell level-10-plus" /><span>&gt;10H</span><i class="cell level-12-plus" /><span>&gt;12H</span><i class="cell future-day" /><span>FUTURE</span><i class="cell exam-day" /><span>EXAM</span>
      </div>
    </div>
    <p class="section-note">Data starts on 23 May 2026. Select a day for its timeline and session titles.</p>
    <div class="heatmap-scroll">
      <div class="weekday-labels"><span>S</span><span>M</span><span>T</span><span>W</span><span>T</span><span>F</span><span>S</span></div>
      <div class="heatmap-grid">
        <button
          v-for="(day, index) in cells"
          :key="day?.date || `empty-${index}`"
          class="heat-cell"
          :class="day ? [heatmapLevelClass(day), { 'future-day': day.is_future, 'exam-day': day.is_exam_day }] : 'empty-cell'"
          :disabled="!day || day.is_future"
          :aria-label="day ? day.is_exam_day ? `${day.date}, exam day` : day.is_future ? `${day.date}, future` : `${day.date}, ${duration(day.minutes)}` : undefined"
          :title="day ? day.is_exam_day ? `${day.date} · EXAM DAY` : day.is_future ? `${day.date} · FUTURE` : `${day.date} · ${duration(day.minutes)} · ${day.sessions} sessions · first ${day.first_start || '--'}` : ''"
          @click="openDay(day)"
        />
      </div>
    </div>

    <el-drawer v-model="detailOpen" size="min(620px, 94vw)" class="day-drawer" destroy-on-close>
      <template #header>
        <div class="dialog-title">
          <div><span class="eyebrow">SESSION BREAKDOWN</span><h2>{{ selected?.date }}</h2></div>
          <div class="day-total"><strong>{{ duration(selected?.minutes || 0) }}</strong><span>{{ selected?.sessions || 0 }} sessions</span></div>
        </div>
      </template>
      <div v-loading="loading">
        <div class="timeline-labels"><span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>24:00</span></div>
        <div class="day-timeline">
          <div v-for="hour in 3" :key="hour" class="timeline-line" :style="{ left: `${hour * 25}%` }" />
          <div
            v-for="session in sessions"
            :key="session.uuid"
            class="online-segment"
            :class="`subject-${session.subject}`"
            :style="timelineStyle(session)"
            :title="`${session.subject_label} ${new Date(session.start_time).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}`"
          />
        </div>
        <div class="online-key"><span><i class="key-online" />STUDY</span><span><i class="key-offline" />OFFLINE</span></div>
        <el-empty v-if="!loading && !sessions.length" description="No completed sessions" :image-size="70" />
        <div v-else class="session-list compact-list">
          <article v-for="session in sessions" :key="session.uuid" class="session-row session-drill-row" role="button" tabindex="0" @click="openSession(session)" @keyup.enter="openSession(session)">
            <i :class="`subject-dot subject-${session.subject}`" />
            <div><strong>{{ session.title || 'Untitled session' }}</strong><small>{{ session.subject_label }} · {{ new Date(session.start_time).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }) }} – {{ session.end_time ? new Date(session.end_time).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }) : '--' }}</small></div>
            <b class="session-review-link"><el-icon><View /></el-icon><span>{{ session.review_count || 0 }}</span></b>
          </article>
        </div>
      </div>
    </el-drawer>

    <el-drawer v-model="sessionOpen" append-to-body size="min(680px, 94vw)" class="session-detail-drawer">
      <template #header>
        <div class="dialog-title"><div><span class="eyebrow">SESSION REVIEW</span><h2>{{ selectedSession?.title || selectedSessionTitle }}</h2></div><el-button v-if="selectedSession" @click="sessionOpen = false; detailOpen = false; router.push(`/sessions/${selectedSession.uuid}`)">Open article</el-button></div>
      </template>
      <div v-if="selectedSession" v-loading="sessionLoading" class="session-detail-page">
        <dl><div><dt>SUBJECT</dt><dd>{{ selectedSession.subject_label }}</dd></div><div><dt>TIME</dt><dd>{{ new Date(selectedSession.start_time).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }) }} – {{ selectedSession.end_time ? new Date(selectedSession.end_time).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }) : '--' }}</dd></div><div><dt>CREDITED</dt><dd>{{ duration(selectedSession.credited_duration_minutes) }} · {{ selectedSession.efficiency_grade }}</dd></div><div><dt>ACTUAL</dt><dd>{{ duration(selectedSession.duration_minutes) }}</dd></div></dl>
        <ReviewTrend :trend="reviewTrend" :loading="sessionLoading" />
        <MarkdownPreview :key="selectedSession.uuid" :source="selectedSession.details" default-open allow-fullscreen empty-text="No details were recorded for this historical session." />
      </div>
      <div v-else v-loading="sessionLoading" class="session-detail-loading" />
    </el-drawer>
  </section>
</template>
