<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../lib/api'
import type { HeatmapDay, Page, StudySession } from '../types'

const props = defineProps<{ days: HeatmapDay[] }>()
const detailOpen = ref(false)
const loading = ref(false)
const selected = ref<HeatmapDay | null>(null)
const sessions = ref<StudySession[]>([])

const cells = computed(() => {
  if (!props.days.length) return []
  const first = new Date(`${props.days[0].date}T00:00:00`).getDay()
  return [...Array.from({ length: first }, () => null), ...props.days]
})

function duration(minutes: number) {
  if (!minutes) return '0 分钟'
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  return `${hours ? `${hours} 小时` : ''}${rest ? ` ${rest} 分钟` : ''}`.trim()
}

function timelineStyle(session: StudySession) {
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
  if (!day) return
  selected.value = day
  detailOpen.value = true
  loading.value = true
  try {
    const result = await api<Page<StudySession>>(`/api/sessions/?date_from=${day.date}&date_to=${day.date}`)
    sessions.value = result.results.filter((item) => item.status === 'completed')
  } catch (error) {
    ElMessage.error((error as Error).message)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <section class="panel heatmap-panel">
    <div class="section-heading">
      <div>
        <span class="eyebrow">CONSISTENCY</span>
        <h2>学习热力图</h2>
      </div>
      <div class="legend" aria-label="热力图图例">
        <span>少</span><i class="cell level-0" /><i class="cell level-1" /><i class="cell level-2" />
        <i class="cell level-4" /><span>≥ 5 小时</span>
      </div>
    </div>
    <p class="section-note">亮绿色表示当天达到 5 小时，和未达标日期保持明显色差。点击任意格子查看当天在线时段。</p>
    <div class="heatmap-scroll">
      <div class="weekday-labels"><span>日</span><span>一</span><span>二</span><span>三</span><span>四</span><span>五</span><span>六</span></div>
      <div class="heatmap-grid">
        <button
          v-for="(day, index) in cells"
          :key="day?.date || `empty-${index}`"
          class="heat-cell"
          :class="day ? `level-${day.level}` : 'empty-cell'"
          :disabled="!day"
          :aria-label="day ? `${day.date}，${duration(day.minutes)}` : undefined"
          :title="day ? `${day.date} · ${duration(day.minutes)} · ${day.sessions} 次 · 首次 ${day.first_start || '--'}` : ''"
          @click="openDay(day)"
        />
      </div>
    </div>

    <el-dialog v-model="detailOpen" width="min(760px, 94vw)" class="day-dialog" destroy-on-close>
      <template #header>
        <div class="dialog-title">
          <div><span class="eyebrow">DAILY TIMELINE</span><h2>{{ selected?.date }}</h2></div>
          <div class="day-total"><strong>{{ duration(selected?.minutes || 0) }}</strong><span>{{ selected?.sessions || 0 }} 次学习</span></div>
        </div>
      </template>
      <div v-loading="loading">
        <div class="timeline-labels"><span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>24:00</span></div>
        <div class="day-timeline">
          <div v-for="hour in 3" :key="hour" class="timeline-line" :style="{ left: `${hour * 25}%` }" />
          <div
            v-for="session in sessions"
            :key="session.id"
            class="online-segment"
            :class="`subject-${session.subject}`"
            :style="timelineStyle(session)"
            :title="`${session.subject_label} ${new Date(session.start_time).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}`"
          />
        </div>
        <div class="online-key"><span><i class="key-online" />在线学习</span><span><i class="key-offline" />未在线</span></div>
        <el-empty v-if="!loading && !sessions.length" description="当天没有已完成的学习记录" :image-size="70" />
        <div v-else class="session-list compact-list">
          <article v-for="session in sessions" :key="session.id" class="session-row">
            <i :class="`subject-dot subject-${session.subject}`" />
            <div><strong>{{ session.subject_label }} · {{ session.topic || session.chapter || '未命名学习' }}</strong><small>{{ new Date(session.start_time).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) }} – {{ session.end_time ? new Date(session.end_time).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) : '--' }}</small></div>
            <b>{{ duration(session.duration_minutes) }}</b>
          </article>
        </div>
      </div>
    </el-dialog>
  </section>
</template>
