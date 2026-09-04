<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { post } from '../lib/api'
import { fetchCatalog } from '../lib/workspace'
import type { Catalog, QuestionSummary } from '../types'
import { useUiPreferences } from '../lib/uiPreferences'

const router = useRouter()
const { t } = useUiPreferences()
const catalog = ref<Catalog | null>(null)
const count = ref(20)
const documentId = ref('')
const topicId = ref('')
const sourceCategory = ref('')
const unattempted = ref(false)
const questions = ref<QuestionSummary[]>([])
const loading = ref(false)
const error = ref('')
const topics = computed(() => catalog.value?.topics.filter((item) => !documentId.value || item.document_id === Number(documentId.value)) || [])

async function generate() {
  loading.value = true
  error.value = ''
  try {
    const result = await post<{ questions: QuestionSummary[] }>('/api/drill/papers/generate/', {
      count: count.value,
      document: documentId.value ? Number(documentId.value) : null,
      topic: topicId.value ? Number(topicId.value) : null,
      source_category: sourceCategory.value,
      unattempted: unattempted.value,
    })
    questions.value = result.questions
    localStorage.setItem('drill.paper.current.v1', JSON.stringify(result.questions))
  } catch (reason) {
    error.value = (reason as Error).message
  } finally {
    loading.value = false
  }
}

function openQuestion(uuid: string) {
  void router.push(`/practice/${uuid}`)
}

function clearPaper() {
  questions.value = []
  localStorage.removeItem('drill.paper.current.v1')
}

onMounted(async () => {
  catalog.value = await fetchCatalog()
  try { questions.value = JSON.parse(localStorage.getItem('drill.paper.current.v1') || '[]') } catch { questions.value = [] }
})
</script>

<template>
  <section class="page paper-page">
    <header class="page-header"><div><span class="eyebrow">{{ t('questionSelection') }}</span><h1>{{ t('customPaper') }}</h1><p>Generated locally for this browser. No duplicate paper rows are stored in the database.</p></div><button class="primary-action" :disabled="loading" @click="generate">{{ loading ? t('generating') : t('generatePaper') }} <b>→</b></button></header>
    <div class="paper-builder filter-panel">
      <label><span>QUESTIONS</span><input v-model.number="count" type="number" min="1" max="100" /></label>
      <label><span>BOOK</span><select v-model="documentId" @change="topicId = ''"><option value="">All books</option><option v-for="item in catalog?.documents" :key="item.id" :value="item.id">{{ item.title }}</option></select></label>
      <label><span>TOPIC</span><select v-model="topicId"><option value="">All topics</option><option v-for="item in topics" :key="item.id" :value="item.id">{{ item.path }}</option></select></label>
      <label><span>SOURCE</span><select v-model="sourceCategory"><option value="">All sources</option><option v-for="item in catalog?.summary.categories" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
      <div class="toggle-row"><button :class="{ active: unattempted }" @click="unattempted = !unattempted">Unattempted only</button></div>
    </div>
    <p v-if="error" class="error-state">{{ error }}</p>
    <div class="result-meta"><span>{{ questions.length }} QUESTIONS IN CURRENT PAPER</span><button v-if="questions.length" @click="clearPaper">CLEAR</button></div>
    <div class="question-list">
      <button v-for="(question, index) in questions" :key="question.uuid" class="question-row" @click="openQuestion(question.uuid)"><span class="question-index">{{ String(index + 1).padStart(2, '0') }}</span><span class="question-copy"><strong>{{ question.display_label || question.source_label }}</strong><small>{{ question.document }} · {{ question.topic || 'General' }}</small></span><span class="source-badge" :class="`category-${question.source_category}`">{{ question.source_category_label }}</span><b class="row-arrow">→</b></button>
      <div v-if="!questions.length && !loading" class="empty-state">Choose filters and generate a paper.</div>
    </div>
  </section>
</template>
