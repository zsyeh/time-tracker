<script setup lang="ts">
import { onMounted, ref } from 'vue'
import ActivityCalendar from '../components/ActivityCalendar.vue'
import { api } from '../lib/api'
import { cachedHeatmap, storeHeatmap } from '../lib/workspace'
import type { ActivityPayload } from '../types'
import { useUiPreferences } from '../lib/uiPreferences'

const activity = ref<ActivityPayload | null>(null)
const { t } = useUiPreferences()
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
  <section class="page activity-page book-checkin-page">
    <header class="page-header activity-page-header">
      <div><span class="eyebrow">{{ t('bookActivity') }}</span><h1>{{ t('bookCheckins') }}</h1><p>Each book has its own July 20–December 19 calendar. Reset events are excluded.</p></div>
      <div class="activity-legend"><span>LESS</span><i v-for="level in 9" :key="level" :class="`activity-level-${level - 1}`" /><span>MORE</span></div>
    </header>
    <p v-if="error" class="error-state">{{ error }}</p>
    <div v-else-if="loading" class="question-skeleton activity-skeleton">BUILDING BOOK CALENDARS…</div>
    <div v-else-if="activity" class="book-activity-list">
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
  </section>
</template>
