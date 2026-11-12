<script setup lang="ts">
import { uiText } from '../lib/uiText'
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../lib/api'
import type { BookFeel } from '../types'
import { useUiPreferences } from '../lib/uiPreferences'

const router = useRouter()
const { t } = useUiPreferences()
const books = ref<BookFeel[]>([])
const loading = ref(true)
const error = ref('')

function relativeCopy(book: BookFeel) {
  if (book.days_idle === null) return 'Not started'
  if (book.days_idle === 0) return 'Practised today'
  return `${book.days_idle} day${book.days_idle === 1 ? '' : 's'} without practice`
}

onMounted(async () => {
  try {
    books.value = (await api<{ books: BookFeel[] }>('/api/drill/feel/')).books
  } catch (reason) {
    error.value = (reason as Error).message
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <section class="page feel-page">
    <header class="page-header"><div><h1>{{ t('bookFeel') }}</h1><p>Today is 0. Each inactive day subtracts one point.</p></div></header>
    <p v-if="error" class="error-state">{{ uiText(error) }}</p>
    <div v-else-if="loading" class="question-skeleton">CALCULATING BOOK FEEL…</div>
    <div v-else class="feel-grid">
      <button v-for="book in books" :key="book.document_id" @click="router.push({ path: '/practice', query: { document: String(book.document_id) } })">
        <span>BOOK</span><h2>{{ book.document }}</h2>
        <strong :class="{ stale: book.feel_score !== null && book.feel_score < 0 }">{{ book.feel_score === null ? '—' : book.feel_score }}</strong>
        <p>{{ relativeCopy(book) }}</p>
        <footer><span>{{ book.recent_attempts }} attempts in 7 days</span><b>Practice →</b></footer>
      </button>
    </div>
  </section>
</template>


<style scoped>
.feel-grid { min-width:0; border:0; border-radius:0; background:transparent; gap:0 24px; display: grid; grid-template-columns: 1fr 1fr; }
.feel-grid > button { min-height: 116px; padding: 14px 16px; border: 0; border-top: 1px solid var(--border-subtle); border-left:0; color: var(--text-primary); background: transparent; display: grid; grid-template: auto auto 1fr auto / 1fr auto; text-align: left; cursor: pointer; }
.feel-grid > button:nth-child(odd) { border-left: 0; }
.feel-grid > button:nth-child(-n+2) { border-top: 0; }
.feel-grid > button:hover { background: var(--bg-surface-hover); }
.feel-grid > button > span { color: var(--text-tertiary); font-size: 12px; }
.feel-grid h2 { grid-column: 1; margin: 3px 0 0; font-size:16px; font-weight:600; }
.feel-grid > button > strong { grid-column: 2; grid-row: 1/3; color:var(--text-primary); font:600 28px var(--font-ui); font-variant-numeric:tabular-nums; }
.feel-grid > button > strong.stale { color: var(--warning); }
.feel-grid p { grid-column: 1/-1; margin: 7px 0; color: var(--text-tertiary); font-size: 12px; }
.feel-grid footer { grid-column: 1/-1; padding-top: 8px; border-top: 1px solid var(--border-subtle); color: var(--text-tertiary); display: flex; justify-content: space-between; font-size: 12px; }
.feel-grid footer b { color: var(--text-secondary); }
@media (max-width: 700px) {
.feel-grid { grid-template-columns: 1fr; }
.feel-grid > button:nth-child(n) { border-top: 1px solid var(--border-subtle); border-left: 0; }
.feel-grid > button:first-child { border-top: 0; }
}
.feel-grid > button { min-width:0; padding:16px 0; } .feel-grid footer { flex-wrap:wrap; gap:8px; } .feel-grid h2 { overflow-wrap:anywhere; }
</style>
