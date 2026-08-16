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
const similarKind = ref<'' | 'past_exam' | 'practice'>('')
const similarCounts = ref({ past_exam: 0, practice: 0 })
const similarLoading = ref(false)
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const similarOpen = ref(false)

async function load() {
  loading.value = true
  error.value = ''
  similarOpen.value = false
  similar.value = []
  similarTopic.value = ''
  similarKind.value = ''
  similarCounts.value = { past_exam: 0, practice: 0 }
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
  similarOpen.value = !similarOpen.value
  if (!similarOpen.value || similarTopic.value) return
  try {
    const response = await api<{ topic: string; counts: { past_exam: number; practice: number }; results: QuestionSummary[] }>(`/api/drill/questions/${props.uuid}/similar/`)
    similarTopic.value = response.topic
    similarCounts.value = response.counts
  } catch (reason) {
    error.value = (reason as Error).message
  }
}

async function loadSimilar(kind: 'past_exam' | 'practice') {
  similarKind.value = kind
  similarLoading.value = true
  similar.value = []
  try {
    const response = await api<{ topic: string; counts: { past_exam: number; practice: number }; results: QuestionSummary[] }>(`/api/drill/questions/${props.uuid}/similar/?kind=${kind}`)
    similarTopic.value = response.topic
    similarCounts.value = response.counts
    similar.value = response.results
  } catch (reason) {
    error.value = (reason as Error).message
  } finally {
    similarLoading.value = false
  }
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
      <div v-if="question.document_author || question.document_attribution" class="source-reference"><span>PDF REFERENCE</span><strong v-if="question.document_author">Author · {{ question.document_author }}</strong><small>{{ question.document_attribution }}</small></div>
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
        <div class="similar-kind-picker">
          <button :class="{ selected: similarKind === 'past_exam' }" :disabled="!similarCounts.past_exam" @click="loadSimilar('past_exam')"><span>OFFICIAL PAST EXAMS</span><strong>{{ similarCounts.past_exam }}</strong><small>Verified exam-source questions</small></button>
          <button :class="{ selected: similarKind === 'practice' }" :disabled="!similarCounts.practice" @click="loadSimilar('practice')"><span>MOCK / PRACTICE</span><strong>{{ similarCounts.practice }}</strong><small>Workbooks, mock papers and other practice</small></button>
        </div>
        <p v-if="!similarKind">Choose which source type to practise.</p>
        <p v-else-if="similarLoading">LOADING SIMILAR QUESTIONS…</p>
        <button v-for="item in similar" :key="item.uuid" @click="router.push(`/practice/${item.uuid}`)"><span>{{ item.display_label || `Question ${item.question_order}` }}</span><small>{{ item.document }} · {{ item.state }} · {{ item.attempt_count }} attempts</small><b>→</b></button>
        <p v-if="similarKind && !similarLoading && !similar.length">No questions of this source type were indexed for this topic.</p>
      </section>
    </template>
  </section>
</template>
