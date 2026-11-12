<script setup lang="ts">
import { uiText } from '../lib/uiText'
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
          :title="`${day.date} · ${day.count} ${day.count === 1 ? 'question' : uiText('questions')}`"
          :aria-label="`${day.date}: ${day.count} questions`"
        />
      </div>
    </div>
  </section>
</template>


<style scoped>
.activity-grid i { width: 11px; height: 11px; border: 1px solid rgba(230, 233, 236, .035); border-radius: 2px; display: block; }
.activity-grid i.future { background:var(--surface-subtle); border-color:var(--border-subtle); }
[data-color-scheme="light"] .activity-grid i.future { background:var(--surface-subtle); border-color:var(--border-subtle); }
.activity-calendar { min-width:0; max-width:100%; margin-bottom:24px; padding:16px 0; border:0; border-top:1px solid var(--border-subtle); border-radius:0; background:transparent; }
.activity-calendar > header { margin-bottom: 13px; display: flex; align-items: flex-end; justify-content: space-between; gap: 18px; }
.activity-calendar > header span { color: var(--text-tertiary); font-size: 12px; }
.activity-calendar h2 { margin: 2px 0 0; font-size:17px; font-weight:600; }
.activity-calendar dl { margin: 0; display: flex; gap: 18px; }
.activity-calendar dl div { text-align: right; }
.activity-calendar dt { color: var(--text-tertiary); font-size: 12px; }
.activity-calendar dd { margin: 2px 0 0; font:600 24px var(--font-ui); font-variant-numeric:tabular-nums; }
.activity-scroll { min-width:0; max-width:100%; overflow-x:auto; display: flex; scrollbar-width: thin; }
.activity-weekdays { margin-right: 6px; color: var(--text-tertiary); display: grid; grid-template-rows: repeat(7, 11px); gap: 3px; font: 12px/12px ui-monospace, monospace; }
.activity-grid { min-width: max-content; display: grid; grid-template-rows: repeat(7, 11px); grid-auto-flow: column; grid-auto-columns: 11px; gap: 3px; }
.activity-placeholder { visibility: hidden; }
@media (max-width: 700px) {
.activity-calendar > header { align-items: flex-start; flex-direction: column; }
.activity-calendar dl { width: 100%; justify-content: space-between; }
.activity-calendar dl div { text-align: left; }
}
@media (max-width: 420px) {
.activity-grid { grid-template-rows: repeat(7, 10px); grid-auto-columns: 10px; }
.activity-grid i { width: 10px; height: 10px; }
.activity-weekdays { grid-template-rows: repeat(7, 10px); line-height: 10px; }
}
</style>
