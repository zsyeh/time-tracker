<script setup lang="ts">
import { uiText } from '../lib/uiText'
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
      <div><h1>Paper history</h1><p>Every generated paper keeps its question set and order.</p></div>
      <RouterLink class="primary-action" to="/papers/new">New paper <b>→</b></RouterLink>
    </header>
    <p v-if="error" class="error-state">{{ uiText(error) }}</p>
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


<style scoped>
.paper-history-list { min-width:0; border:0; border-top:1px solid var(--border-subtle); border-radius:0; background:transparent; }
.paper-history-row { min-height: 66px; padding: 11px 14px; border-bottom: 1px solid var(--border-subtle); display: grid; grid-template-columns: 80px minmax(0, 1fr) 90px auto; align-items: center; gap: 14px; }
.paper-history-row:last-child { border-bottom: 0; }
.paper-mode { color: var(--text-tertiary); font-size:13px; text-transform: uppercase; }
.paper-history-row > div { min-width: 0; display: grid; gap: 4px; }
.paper-history-row strong { font-size:13px; }
.paper-history-row small { color: var(--text-tertiary); font-size:13px; }
.paper-history-progress { text-align: right; }
.paper-history-actions { display: flex !important; grid-auto-flow: column; gap:8px !important; }
.paper-history-actions a { padding: 6px 8px; border:0; border-radius: var(--radius-sm); color: var(--text-secondary); background: transparent; text-decoration: none; font-size:13px; cursor: pointer; }
.paper-history-actions a:hover { border-color: var(--border-default); color: var(--text-primary); background: var(--bg-surface-hover); }
@media (max-width: 700px) {
.paper-history-row { grid-template-columns: 1fr auto; }
.paper-history-row > .paper-mode { display: none; }
.paper-history-progress { grid-column: 2; grid-row: 1; }
.paper-history-actions { grid-column: 1/-1; }
}
.paper-history-row { min-width:0; } .paper-history-row strong { font-size:14px; } .paper-history-actions a { min-height:44px; display:inline-flex; align-items:center; background:var(--surface-subtle); }
</style>
