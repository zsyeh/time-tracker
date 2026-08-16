<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../lib/api'
import type { Catalog, Page, QuestionSummary } from '../types'

const router = useRouter()
const catalog = ref<Catalog>({
  summary: { imported_count: 0, practiceable_count: 0, outline_count: 0, categories: [] },
  coverage: { available: [], missing: [], source_archive_checked: false },
  documents: [],
  topics: [],
})
const questions = ref<Page<QuestionSummary> | null>(null)
const loading = ref(true)
const error = ref('')
const documentId = ref('')
const topicId = ref('')
const search = ref('')
const sourceCategory = ref('')
const unattempted = ref(false)
const page = ref(1)
let searchTimer = 0

const topics = computed(() => catalog.value.topics.filter((topic) => (
  !documentId.value || topic.document_id === Number(documentId.value)
)))
const topicGroups = computed(() => catalog.value.documents.map((document) => ({
  document,
  topics: topics.value.filter((topic) => topic.document_id === document.id),
})).filter((group) => group.topics.length))
const categoryOptions = computed(() => catalog.value.summary.categories.filter((item) => item.count > 0))

async function loadQuestions() {
  loading.value = true
  error.value = ''
  const params = new URLSearchParams({ page: String(page.value) })
  if (documentId.value) params.set('document', documentId.value)
  if (topicId.value) params.set('topic', topicId.value)
  if (search.value.trim()) params.set('q', search.value.trim())
  if (sourceCategory.value) params.set('source_category', sourceCategory.value)
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
watch([topicId, sourceCategory, unattempted], filtersChanged)

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
      <div><span class="eyebrow">CLEANED QUESTION INDEX</span><h1>Know what you are practising.</h1><p>{{ catalog.summary.practiceable_count.toLocaleString() }} practice records. {{ catalog.summary.outline_count.toLocaleString() }} source-outline rows are hidden.</p></div>
      <button v-if="questions?.results.length" class="primary-action" @click="router.push(`/practice/${questions.results[0].uuid}`)">Open next question <b>→</b></button>
    </header>

    <div class="taxonomy-grid">
      <button :class="{ active: sourceCategory === '' }" @click="sourceCategory = ''"><span>ALL PRACTICE</span><strong>{{ catalog.summary.practiceable_count.toLocaleString() }}</strong><small>cleaned records</small></button>
      <button v-for="item in categoryOptions" :key="item.value" :class="[`category-${item.value}`, { active: sourceCategory === item.value }]" @click="sourceCategory = item.value"><span>{{ item.label.toUpperCase() }}</span><strong>{{ item.count.toLocaleString() }}</strong><small>{{ item.value === 'past_exam' ? 'verified official source' : 'source-labelled records' }}</small></button>
    </div>

    <aside v-if="catalog.coverage.missing.length" class="source-gap"><strong>SOURCE GAP</strong><span>{{ catalog.coverage.missing.join(', ') }} is not present in <code>Downloads.7z</code>. It is not hidden by a filter.</span></aside>

    <div class="filter-panel">
      <label class="search-field"><span>SEARCH</span><input v-model="search" placeholder="Source, topic, or question text" @input="searchChanged" /></label>
      <label><span>BOOK</span><select v-model="documentId"><option value="">All books</option><option v-for="item in catalog.documents" :key="item.id" :value="item.id">{{ item.title }} · {{ item.question_count }}</option></select></label>
      <label><span>TOPIC PATH</span><select v-model="topicId"><option value="">All topics</option><optgroup v-for="group in topicGroups" :key="group.document.id" :label="group.document.title"><option v-for="item in group.topics" :key="item.id" :value="item.id">{{ item.path }} · {{ item.question_count }}</option></optgroup></select></label>
      <div class="toggle-row"><button :class="{ active: unattempted }" @click="unattempted = !unattempted">Unattempted</button></div>
    </div>

    <div class="result-meta"><span>{{ questions?.count ?? 0 }} PRACTICE RECORDS</span><span class="state-legend"><i class="status-unattempted" /> NOT STARTED <i class="status-mastered" /> MASTERED <i class="status-review" /> REVIEW</span><span v-if="loading">LOADING…</span></div>
    <p v-if="error" class="error-state">{{ error }}</p>
    <div v-else class="question-list" :class="{ loading }">
      <button v-for="question in questions?.results" :key="question.uuid" class="question-row" @click="router.push(`/practice/${question.uuid}`)">
        <span class="question-index">{{ String(question.question_order).padStart(4, '0') }}</span>
        <span class="question-copy"><strong>{{ question.display_label || `Question ${question.question_order}` }}</strong><small>{{ question.document }} · {{ question.topic || 'General' }}<em v-if="question.record_kind === 'grouped'"> · grouped extract</em></small></span>
        <span class="source-badge" :class="`category-${question.source_category}`">{{ question.source_category_label }}</span>
        <span class="attempt-mark" :class="`status-${question.state}`" :title="`${question.state}; ${question.attempt_count} recorded attempts`">{{ question.attempt_count || '' }}</span>
        <b class="row-arrow">→</b>
      </button>
      <div v-if="!loading && !questions?.results.length" class="empty-state">No questions match these filters.</div>
    </div>
    <footer v-if="questions && (questions.previous || questions.next)" class="pager"><button :disabled="!questions.previous" @click="page--; loadQuestions()">← Previous</button><span>PAGE {{ page }}</span><button :disabled="!questions.next" @click="page++; loadQuestions()">Next →</button></footer>
  </section>
</template>
