<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../lib/api'
import type { ExamPaperSummary } from '../types'

const papers = ref<ExamPaperSummary[]>([])
const loading = ref(true)
const error = ref('')

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

onMounted(async () => {
  try {
    papers.value = (await api<{ results: ExamPaperSummary[] }>('/api/drill/papers/')).results
  } catch (reason) {
    error.value = (reason as Error).message
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <section class="page papers-page">
    <header class="page-header">
      <div><span class="eyebrow">MATH II</span><h1>Paper history</h1><p>Every generated paper keeps its question set and order.</p></div>
      <RouterLink class="primary-action" to="/papers/new">New paper <b>→</b></RouterLink>
    </header>
    <p v-if="error" class="error-state">{{ error }}</p>
    <div class="paper-history-list">
      <article v-for="paper in papers" :key="paper.uuid" class="paper-history-row">
        <span class="paper-mode">{{ paper.mode }}</span>
        <div><strong>{{ paper.title }}</strong><small>{{ formatDate(paper.created_at) }} · {{ paper.question_count }} questions · {{ paper.duration_minutes }} min</small></div>
        <div class="paper-history-progress"><strong>{{ paper.answered_count }}/{{ paper.question_count }}</strong><small>{{ paper.status.replace('_', ' ') }}</small></div>
        <div class="paper-history-actions">
          <RouterLink :to="`/papers/${paper.uuid}`">Open</RouterLink>
          <RouterLink :to="`/papers/${paper.uuid}/review`">Review</RouterLink>
        </div>
      </article>
      <div v-if="!loading && !papers.length" class="empty-state">No papers yet. Generate one when you are ready to work.</div>
    </div>
  </section>
</template>
