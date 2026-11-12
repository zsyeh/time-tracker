<script setup lang="ts">
import { uiText } from '../lib/uiText'
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
      <div><h1>{{ t('practiceActivity') }}</h1><p>Daily volume from July 20 through December 19. Reset events are excluded.</p></div>
      <div class="activity-legend"><span>LESS</span><i v-for="level in 9" :key="level" :class="`activity-level-${level - 1}`" /><span>MORE</span></div>
    </header>
    <p v-if="error" class="error-state">{{ uiText(error) }}</p>
    <div v-else-if="loading" class="question-skeleton activity-skeleton">BUILDING ACTIVITY…</div>
    <template v-else-if="activity">
      <ActivityCalendar
        eyebrow="ALL BOOKS"
        :title="uiText('All practice')"
        :total-attempts="activity.overall.total_attempts"
        :active-days="activity.overall.active_days"
        :max-daily-count="activity.overall.max_daily_count"
        :days="activity.overall.days"
      />
      <RouterLink class="activity-route-card" to="/book-activity"><span>BOOK CHECK-INS</span><strong>Open {{ activity.books.length }} individual calendars</strong><b>→</b></RouterLink>
    </template>
  </section>
</template>


<style scoped>
.activity-route-card { min-height: 48px; padding: 10px 13px; border:0; border-top:1px solid var(--border-subtle); border-radius:0; color: var(--text-primary); background: var(--bg-surface); text-decoration: none; display: grid; grid-template: auto auto / 1fr auto; }
.activity-route-card:hover { border-color: var(--border-default); background: var(--bg-surface-hover); }
.activity-route-card span { color: var(--text-tertiary); font-size:13px; }
.activity-route-card strong { margin-top: 2px; font-size:13px; }
.activity-route-card b { grid-column: 2; grid-row: 1/3; align-self: center; color: var(--accent); }
</style>
