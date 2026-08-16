<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../lib/api'
import type { Catalog, Page, QuestionSummary } from '../types'

const router = useRouter()
const catalog = ref<Catalog>({ documents: [], topics: [] })
const questions = ref<Page<QuestionSummary> | null>(null)
const loading = ref(true)
const error = ref('')
const documentId = ref('')
const topicId = ref('')
const search = ref('')
const pastOnly = ref(false)
const unattempted = ref(false)
const page = ref(1)
let searchTimer = 0

const topics = computed(() => catalog.value.topics.filter((topic) => (
  !documentId.value || topic.document_id === Number(documentId.value)
)))
const totalQuestions = computed(() => catalog.value.documents.reduce(
  (total, document) => total + document.question_count, 0,
))

function level(count: number) {
  return Math.min(4, count)
}

async function loadQuestions() {
  loading.value = true
  error.value = ''
  const params = new URLSearchParams({ page: String(page.value) })
  if (documentId.value) params.set('document', documentId.value)
  if (topicId.value) params.set('topic', topicId.value)
  if (search.value.trim()) params.set('q', search.value.trim())
  if (pastOnly.value) params.set('past_exam', '1')
  if (unattempted.value) params.set('unattempted', '1')
  try {
    questions.value = await api(`/api/drill/questions/?${params}`)
  } catch (reason) {
    error.value = (reason as Error).message
  } finally {
    loading.value = false
  }
}

function filtersChanged() {
  page.value = 1
  void loadQuestions()
}

function searchChanged() {
  window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(filtersChanged, 250)
}

watch(documentId, () => {
  if (!topics.value.some((topic) => String(topic.id) === topicId.value)) topicId.value = ''
  filtersChanged()
})
watch([topicId, pastOnly, unattempted], filtersChanged)

onMounted(async () => {
  try {
    catalog.value = await api('/api/drill/catalog/')
    await loadQuestions()
  } catch (reason) {
    error.value = (reason as Error).message
    loading.value = false
  }
})
</script>

<template>
  <section class="page practice-page">
    <header class="page-header">
      <div><span class="eyebrow">QUESTION BANK</span><h1>Practice with intent.</h1><p>{{ totalQuestions.toLocaleString() }} indexed questions, grouped by their actual knowledge structure.</p></div>
      <button v-if="questions?.results.length" class="primary-action" @click="router.push(`/practice/${questions.results[0].uuid}`)">Open next question <b>→</b></button>
    </header>

    <div class="filter-panel">
      <label class="search-field"><span>SEARCH</span><input v-model="search" placeholder="Source, topic, or question text" @input="searchChanged" /></label>
      <label><span>BOOK</span><select v-model="documentId"><option value="">All books</option><option v-for="item in catalog.documents" :key="item.id" :value="item.id">{{ item.title }} · {{ item.question_count }}</option></select></label>
      <label><span>TOPIC</span><select v-model="topicId"><option value="">All topics</option><option v-for="item in topics" :key="item.id" :value="item.id">{{ item.title }} · {{ item.question_count }}</option></select></label>
      <div class="toggle-row"><button :class="{ active: pastOnly }" @click="pastOnly = !pastOnly">Past papers</button><button :class="{ active: unattempted }" @click="unattempted = !unattempted">Unattempted</button></div>
    </div>

    <div class="result-meta"><span>{{ questions?.count ?? 0 }} QUESTIONS</span><span v-if="loading">LOADING…</span></div>
    <p v-if="error" class="error-state">{{ error }}</p>
    <div v-else class="question-list" :class="{ loading }">
      <button v-for="question in questions?.results" :key="question.uuid" class="question-row" @click="router.push(`/practice/${question.uuid}`)">
        <span class="question-index">{{ String(question.question_order).padStart(4, '0') }}</span>
        <span class="question-copy"><strong>{{ question.source_label || `Question ${question.question_order}` }}</strong><small>{{ question.document }} · {{ question.topic || 'General' }}</small></span>
        <span v-if="question.is_past_exam" class="past-badge">{{ question.exam_year }} {{ question.exam_variant }}</span>
        <span class="attempt-mark" :class="`level-${level(question.attempt_count)}`" :title="`${question.attempt_count} attempts`">{{ question.attempt_count || '' }}</span>
        <b class="row-arrow">→</b>
      </button>
      <div v-if="!loading && !questions?.results.length" class="empty-state">No questions match these filters.</div>
    </div>
    <footer v-if="questions && (questions.previous || questions.next)" class="pager"><button :disabled="!questions.previous" @click="page--; loadQuestions()">← Previous</button><span>PAGE {{ page }}</span><button :disabled="!questions.next" @click="page++; loadQuestions()">Next →</button></footer>
  </section>
</template>
