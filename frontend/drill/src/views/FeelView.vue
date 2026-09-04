<script setup lang="ts">
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
    <header class="page-header"><div><span class="eyebrow">{{ t('practiceRecency') }}</span><h1>{{ t('bookFeel') }}</h1><p>Today is 0. Each inactive day subtracts one point.</p></div></header>
    <p v-if="error" class="error-state">{{ error }}</p>
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
