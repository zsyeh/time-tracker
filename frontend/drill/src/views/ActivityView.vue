<script setup lang="ts">
import { onMounted, ref } from 'vue'
import ActivityCalendar from '../components/ActivityCalendar.vue'
import { api } from '../lib/api'
import { cachedHeatmap, storeHeatmap } from '../lib/workspace'

interface ActivityCalendarData {
  total_attempts: number
  active_days: number
  max_daily_count: number
  days: Array<{ date: string; count: number; level: number; is_future: boolean }>
}

interface ActivityPayload {
  start_date: string
  end_date: string
  today: string
  overall: ActivityCalendarData
  books: Array<ActivityCalendarData & { document_id: number; document: string }>
}

const activity = ref<ActivityPayload | null>(null)
const loading = ref(true)
const error = ref('')

async function load() {
  const cacheKey = 'activity'
  const cached = cachedHeatmap<ActivityPayload>(cacheKey)
  if (cached) activity.value = cached
  loading.value = !cached
  error.value = ''
  try {
    const value = await api<ActivityPayload>('/api/drill/heatmap/activity/')
    activity.value = value
    storeHeatmap(cacheKey, value)
  } catch (reason) {
    error.value = (reason as Error).message
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <section class="page activity-page">
    <header class="page-header activity-page-header">
      <div><span class="eyebrow">DAILY PRACTICE</span><h1>Practice activity.</h1><p>Daily volume from July 20 through December 19. Reset events are excluded.</p></div>
      <div class="activity-legend"><span>LESS</span><i v-for="level in 9" :key="level" :class="`activity-level-${level - 1}`" /><span>MORE</span></div>
    </header>
    <p v-if="error" class="error-state">{{ error }}</p>
    <div v-else-if="loading" class="question-skeleton activity-skeleton">BUILDING ACTIVITY…</div>
    <template v-else-if="activity">
      <ActivityCalendar
        eyebrow="ALL BOOKS"
        title="All practice"
        :total-attempts="activity.overall.total_attempts"
        :active-days="activity.overall.active_days"
        :max-daily-count="activity.overall.max_daily_count"
        :days="activity.overall.days"
      />
      <div class="book-activity-grid">
        <ActivityCalendar
          v-for="book in activity.books"
          :key="book.document_id"
          eyebrow="BOOK"
          :title="book.document"
          :total-attempts="book.total_attempts"
          :active-days="book.active_days"
          :max-daily-count="book.max_daily_count"
          :days="book.days"
        />
      </div>
    </template>
  </section>
</template>
