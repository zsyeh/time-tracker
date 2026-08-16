<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api, post, remove } from '../lib/api'
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

interface StateResponse {
  attempt_count: number
  latest_result: QuestionDetail['latest_result']
  state: QuestionDetail['state']
  can_undo: boolean
}

function applyState(response: StateResponse) {
  if (!question.value) return
  question.value.attempt_count = response.attempt_count
  question.value.latest_result = response.latest_result
  question.value.state = response.state
  question.value.can_undo = response.can_undo
}

async function record(result: 'correct' | 'review' | 'reset') {
  saving.value = true
  try {
    applyState(await post<StateResponse>(`/api/drill/questions/${props.uuid}/attempts/`, { result }))
  } catch (reason) {
    error.value = (reason as Error).message
  } finally {
    saving.value = false
  }
}

async function undo() {
  saving.value = true
  try {
    applyState(await remove<StateResponse>(`/api/drill/questions/${props.uuid}/attempts/`))
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
        <div><span class="eyebrow">{{ question.document }} · {{ String(question.question_order).padStart(4, '0') }}</span><h1>{{ question.display_label || `Question ${question.question_order}` }}</h1><p>{{ question.breadcrumbs.map((item) => item.title).join(' / ') }}</p><div class="question-badges"><span class="source-badge" :class="`category-${question.source_category}`">{{ question.source_category_label }}</span><span v-if="question.record_kind === 'grouped'" class="source-badge">Grouped source extract</span></div></div>
        <div class="attempt-counter"><span>CURRENT STATE</span><strong class="state-name" :class="`text-${question.state}`">{{ question.state === 'mastered' ? 'MASTERED' : question.state === 'review' ? 'REVIEW' : 'NOT STARTED' }}</strong><small>{{ question.attempt_count }} recorded attempts</small></div>
      </header>

      <div class="render-note"><span>RENDER SOURCE</span><strong>{{ question.formula_source === 'tex' ? 'Structured TeX' : 'Original PDF crop' }}</strong><small v-if="question.formula_source !== 'tex'">The source PDF does not expose recoverable TeX. The lossless crop preserves formula fidelity.</small></div>
      <article class="question-canvas">
        <img v-for="asset in question.assets" :key="asset.id" :src="asset.url" :width="asset.width" :height="asset.height" alt="Question content" loading="eager" decoding="async" />
        <pre v-if="!question.assets.length">{{ question.prompt_text }}</pre>
      </article>

      <div class="answer-bar">
        <div><span>QUESTION STATE</span><small>Grey = not started, green = mastered, yellow = needs review. You can change, reset, or undo at any time.</small></div>
        <div><button class="review" :class="{ selected: question.state === 'review' }" :disabled="saving" @click="record('review')">Needs review</button><button class="correct" :class="{ selected: question.state === 'mastered' }" :disabled="saving" @click="record('correct')">Mastered</button><button :disabled="saving || question.state === 'unattempted'" @click="record('reset')">Reset</button><button :disabled="saving || !question.can_undo" @click="undo">Undo</button></div>
      </div>

      <details v-if="question.source_label && question.source_label !== question.display_label" class="raw-provenance"><summary>View original imported label</summary><code>{{ question.source_label }}</code></details>

      <button class="similar-trigger" @click="showSimilar"><span>Practice similar questions</span><small>Same indexed knowledge topic</small><b>{{ similarOpen ? '↓' : '→' }}</b></button>
      <section v-if="similarOpen" class="similar-panel">
        <header><span>SIMILAR SET</span><strong>{{ similarTopic || 'No indexed topic' }}</strong></header>
        <button v-for="item in similar" :key="item.uuid" @click="router.push(`/practice/${item.uuid}`)"><span>{{ item.display_label || `Question ${item.question_order}` }}</span><small>{{ item.document }} · {{ item.state }} · {{ item.attempt_count }} attempts</small><b>→</b></button>
        <p v-if="!similar.length">No similar questions were indexed for this item.</p>
      </section>
    </template>
  </section>
</template>
