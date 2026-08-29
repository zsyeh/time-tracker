<script setup lang="ts">
import { computed } from 'vue'

interface ActivityDay {
  date: string
  count: number
  level: number
  is_future: boolean
}

const props = defineProps<{
  title: string
  eyebrow: string
  totalAttempts: number
  activeDays: number
  maxDailyCount: number
  days: ActivityDay[]
}>()

const startOffset = computed(() => {
  const firstDate = props.days[0]?.date
  return firstDate ? new Date(`${firstDate}T00:00:00Z`).getUTCDay() : 0
})
</script>

<template>
  <section class="activity-calendar">
    <header>
      <div><span>{{ eyebrow }}</span><h2>{{ title }}</h2></div>
      <dl>
        <div><dt>ATTEMPTS</dt><dd>{{ totalAttempts }}</dd></div>
        <div><dt>ACTIVE DAYS</dt><dd>{{ activeDays }}</dd></div>
        <div><dt>DAILY HIGH</dt><dd>{{ maxDailyCount }}</dd></div>
      </dl>
    </header>
    <div class="activity-scroll">
      <div class="activity-weekdays" aria-hidden="true"><span>S</span><span /><span>T</span><span /><span>T</span><span /><span>S</span></div>
      <div class="activity-grid" role="img" :aria-label="`${title} activity calendar`">
        <i v-for="offset in startOffset" :key="`offset-${offset}`" class="activity-placeholder" aria-hidden="true" />
        <i
          v-for="day in days"
          :key="day.date"
          :class="[`activity-level-${day.level}`, { future: day.is_future }]"
          :title="`${day.date} · ${day.count} ${day.count === 1 ? 'question' : 'questions'}`"
          :aria-label="`${day.date}: ${day.count} questions`"
        />
      </div>
    </div>
  </section>
</template>
