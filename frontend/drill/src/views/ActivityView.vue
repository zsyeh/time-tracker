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
  <section class="page activity-page">
    <header class="page-header activity-page-header">
      <div><span class="eyebrow">{{ t('dailyPractice') }}</span><h1>{{ t('practiceActivity') }}</h1><p>Daily volume from July 20 through December 19. Reset events are excluded.</p></div>
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
      <RouterLink class="activity-route-card" to="/book-activity"><span>BOOK CHECK-INS</span><strong>Open {{ activity.books.length }} individual calendars</strong><b>→</b></RouterLink>
    </template>
  </section>
</template>
