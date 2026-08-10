<script setup lang="ts">
import { computed } from 'vue'
import { View } from '@element-plus/icons-vue'
import type { ReviewTrend } from '../types'

const props = defineProps<{ trend: ReviewTrend | null; loading?: boolean }>()

const bars = computed(() => {
  const counts = new Map((props.trend?.daily || []).map((item) => [item.date, item.count]))
  const output: Array<{ date: string; count: number }> = []
  const cursor = new Date()
  cursor.setHours(12, 0, 0, 0)
  for (let offset = 27; offset >= 0; offset -= 1) {
    const date = new Date(cursor)
    date.setDate(cursor.getDate() - offset)
    const key = date.toLocaleDateString('en-CA')
    output.push({ date: key, count: counts.get(key) || 0 })
  }
  return output
})
const maximum = computed(() => Math.max(1, ...bars.value.map((item) => item.count)))
</script>

<template>
  <section class="review-trend" v-loading="loading">
    <div class="review-trend-heading">
      <div><el-icon><View /></el-icon><span>REVIEW TREND</span></div>
      <strong>{{ trend?.total || 0 }}<small> reviews</small></strong>
    </div>
    <div class="review-bars" aria-label="Review activity over the last 28 days">
      <i v-for="item in bars" :key="item.date" :class="{ active: item.count > 0 }" :style="{ height: `${Math.max(3, item.count / maximum * 28)}px` }" :title="`${item.date} · ${item.count} reviews`" />
    </div>
    <div class="review-trend-meta"><span>28 DAYS</span><span>{{ trend?.review_days || 0 }} ACTIVE DAYS</span><span>LAST {{ trend?.last_reviewed_at ? new Date(trend.last_reviewed_at).toLocaleDateString('en-CA') : '--' }}</span></div>
  </section>
</template>
