<script setup lang="ts">
import { computed } from 'vue'
import { heatmapProgress } from '../lib/heatmapProgress'

const props = defineProps<{ total: number; attempted: number; mastered: number }>()
const progress = computed(() => heatmapProgress(props.total, props.attempted, props.mastered))
</script>

<template>
  <dl class="heatmap-progress" aria-label="题目掌握统计">
    <div data-progress="attempted"><dt>已做</dt><dd>{{ progress.attempted }}</dd></div>
    <div data-progress="unattempted"><dt>未做</dt><dd>{{ progress.unattempted }}</dd></div>
    <div data-progress="mastered"><dt>已掌握</dt><dd>{{ progress.mastered }}</dd></div>
    <div data-progress="attempted-rate" title="已掌握题数 ÷ 已做题数"><dt>已做掌握率</dt><dd>{{ progress.attemptedMasterRate }}</dd><small>{{ mastered }} / {{ attempted }}</small></div>
    <div data-progress="total-rate" title="已掌握题数 ÷ 当前范围总题数"><dt>总掌握率</dt><dd>{{ progress.totalMasterRate }}</dd><small>{{ mastered }} / {{ total }}</small></div>
  </dl>
</template>

<style scoped>
.heatmap-progress { margin: 0 0 9px; display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); background: var(--bg-surface); }
.heatmap-progress > div { min-width: 0; padding: 12px; border-left: 1px solid var(--border-subtle); }
.heatmap-progress > div:first-child { border-left: 0; }
.heatmap-progress dt { font-size: 12px; color: var(--text-secondary); }
.heatmap-progress dd { margin: 5px 0 0; color: var(--text-primary); font: 570 20px ui-monospace, monospace; font-variant-numeric: tabular-nums; }
.heatmap-progress small { display: block; margin-top: 4px; color: var(--text-tertiary); font-size: 11px; }
@media (max-width: 600px) {
  .heatmap-progress { grid-template-columns: repeat(6, minmax(0, 1fr)); }
  .heatmap-progress > div { grid-column: span 2; padding: 10px; }
  .heatmap-progress > div:nth-child(n+4) { grid-column: span 3; border-top: 1px solid var(--border-subtle); }
  .heatmap-progress > div:nth-child(4) { border-left: 0; }
}
</style>
