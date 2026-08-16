<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api, post } from '../lib/api'
import type { QuestionDetail, QuestionSummary } from '../types'

const props = defineProps<{ uuid: string }>()
const router = useRouter()
const question = ref<QuestionDetail | null>(null)
const similar = ref<QuestionSummary[]>([])
const similarTopic = ref('')
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const similarOpen = ref(false)

async function load() {
  loading.value = true
  error.value = ''
  similarOpen.value = false
  similar.value = []
  try {
    question.value = await api(`/api/drill/questions/${props.uuid}/`)
  } catch (reason) {
    error.value = (reason as Error).message
  } finally {
    loading.value = false
  }
}

async function record(result: 'done' | 'correct' | 'review') {
  saving.value = true
  try {
    const response = await post<{ attempt_count: number; result: QuestionDetail['latest_result'] }>(`/api/drill/questions/${props.uuid}/attempts/`, { result })
    if (question.value) {
      question.value.attempt_count = response.attempt_count
      question.value.latest_result = response.result
    }
  } catch (reason) {
    error.value = (reason as Error).message
  } finally {
    saving.value = false
  }
}

async function showSimilar() {
  similarOpen.value = true
  if (similar.value.length) return
  const response = await api<{ topic: string; results: QuestionSummary[] }>(`/api/drill/questions/${props.uuid}/similar/`)
  similarTopic.value = response.topic
  similar.value = response.results
}

watch(() => props.uuid, load)
onMounted(load)
</script>

<template>
  <section class="page question-page">
    <button class="back-link" @click="router.push('/practice')">← Question bank</button>
    <p v-if="error" class="error-state">{{ error }}</p>
    <div v-if="loading" class="question-skeleton">LOADING QUESTION…</div>
    <template v-else-if="question">
      <header class="question-header">
        <div><span class="eyebrow">{{ question.document }} · {{ String(question.question_order).padStart(4, '0') }}</span><h1>{{ question.source_label || `Question ${question.question_order}` }}</h1><p>{{ question.breadcrumbs.map((item) => item.title).join(' / ') }}</p></div>
        <div class="attempt-counter"><span>ATTEMPTS</span><strong>{{ question.attempt_count }}</strong><small>{{ question.latest_result?.replace('_', ' ') || 'not attempted' }}</small></div>
      </header>

      <article class="question-canvas">
        <img v-for="asset in question.assets" :key="asset.id" :src="asset.url" :width="asset.width" :height="asset.height" alt="Question content" loading="eager" decoding="async" />
        <pre v-if="!question.assets.length">{{ question.prompt_text }}</pre>
      </article>

      <div class="answer-bar">
        <div><span>RECORD THIS ATTEMPT</span><small>Choose one result. Each click adds one practice frequency.</small></div>
        <div><button :disabled="saving" @click="record('review')">Needs review</button><button :disabled="saving" @click="record('done')">Done</button><button class="correct" :disabled="saving" @click="record('correct')">Correct</button></div>
      </div>

      <button class="similar-trigger" @click="showSimilar"><span>Practice similar questions</span><small>Same indexed knowledge topic</small><b>{{ similarOpen ? '↓' : '→' }}</b></button>
      <section v-if="similarOpen" class="similar-panel">
        <header><span>SIMILAR SET</span><strong>{{ similarTopic || 'No indexed topic' }}</strong></header>
        <button v-for="item in similar" :key="item.uuid" @click="router.push(`/practice/${item.uuid}`)"><span>{{ item.source_label || `Question ${item.question_order}` }}</span><small>{{ item.document }} · {{ item.attempt_count }} attempts</small><b>→</b></button>
        <p v-if="!similar.length">No similar questions were indexed for this item.</p>
      </section>
    </template>
  </section>
</template>

