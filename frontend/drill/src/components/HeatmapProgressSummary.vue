<script setup lang="ts">
import { computed } from 'vue'
import { uiText } from '../lib/uiText'

const props = defineProps<{
  total: number
  statistics: { attempted_question_count: number; mastered_question_count: number; review_question_count: number }
}>()
const rows = computed(() => [
  { label: '已做', count: props.statistics.attempted_question_count },
  { label: '已掌握', count: props.statistics.mastered_question_count },
  { label: '未做', count: Math.max(0, props.total - props.statistics.attempted_question_count) },
  { label: '待复习', count: props.statistics.review_question_count },
])
const percent = (count: number) => props.total ? `${Math.round(count * 1000 / props.total) / 10}%` : '0%'
</script>

<template>
  <dl class="heatmap-progress-summary">
    <div v-for="row in rows" :key="row.label">
      <dt>{{ uiText(row.label) }}</dt>
      <dd><strong>{{ row.count }} / {{ total }}</strong><span>{{ percent(row.count) }}</span></dd>
    </div>
  </dl>
</template>

<style scoped>
.heatmap-progress-summary { display: flex; flex-wrap: wrap; gap: 8px 24px; margin: 0; font-size: 13px; font-variant-numeric: tabular-nums; }
.heatmap-progress-summary > div { display: flex; align-items: baseline; flex-wrap: wrap; gap: 4px 8px; }
.heatmap-progress-summary dt { color: var(--text-secondary); }
.heatmap-progress-summary dd { display: flex; align-items: baseline; gap: 8px; margin: 0; }
.heatmap-progress-summary strong { color: var(--text-primary); font-weight: 650; white-space: nowrap; }
.heatmap-progress-summary dd span { color: var(--text-secondary); white-space: nowrap; }
@media (max-width: 700px) {
  .heatmap-progress-summary { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 16px; }
}
</style>
