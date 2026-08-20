<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../lib/api'
import { cachedHeatmap, storeHeatmap } from '../lib/workspace'

interface HeatmapQuestion {
  uuid: string
  order: number
  label: string
  topic: string
  year: number | null
  variant: string
  attempt_count: number
  latest_result: string | null
  state: 'unattempted' | 'mastered' | 'review'
}

interface HeatmapTopic {
  topic_id: number
  topic: string
  path: string
  question_count: number
  attempted_question_count: number
  mastered_question_count: number
  review_question_count: number
  attempt_count: number
  coverage_percent: number
  intensity: 0 | 1 | 2 | 3 | 4
  state: 'unattempted' | 'progress' | 'mastered' | 'review'
}

interface HeatmapPayload {
  question_count: number
  topic_count: number
  groups: Array<{
    document_id: number
    document: string
    questions: HeatmapQuestion[]
    topics: HeatmapTopic[]
  }>
}

const router = useRouter()
const data = ref<HeatmapPayload | null>(null)
const loading = ref(true)
const error = ref('')
const scope = ref<'past_exam' | 'mock_exam' | 'all'>('all')
const mode = ref<'topics' | 'questions'>('topics')

function openTopic(documentId: number, topicId: number) {
  void router.push({
    path: '/practice',
    query: { document: String(documentId), topic: String(topicId) },
  })
}

async function load() {
  const requestedScope = scope.value
  const requestedMode = mode.value
  const cacheKey = `${requestedMode}:${requestedScope}`
  const cached = cachedHeatmap<HeatmapPayload>(cacheKey)
  if (cached) data.value = cached
  loading.value = !cached
  error.value = ''
  try {
    const value = await api<HeatmapPayload>(`/api/drill/heatmap/?scope=${requestedScope}&mode=${requestedMode}`)
    if (scope.value !== requestedScope || mode.value !== requestedMode) return
    data.value = value
    storeHeatmap(cacheKey, value)
  } catch (reason) {
    error.value = (reason as Error).message
  } finally {
    if (scope.value === requestedScope && mode.value === requestedMode) loading.value = false
  }
}

watch([scope, mode], load)
onMounted(load)
</script>

<template>
  <section class="page heatmap-page">
    <header class="page-header">
      <div><span class="eyebrow">KNOWLEDGE COVERAGE</span><h1>One map for every book.</h1><p>Each cell is one indexed knowledge topic. Open a cell to practice that topic, or switch back to the question-level map.</p></div>
      <div class="heat-controls">
        <div class="heat-mode"><button :class="{ active: mode === 'topics' }" @click="mode = 'topics'">Topics</button><button :class="{ active: mode === 'questions' }" @click="mode = 'questions'">Questions</button></div>
        <div class="heat-scope"><button :class="{ active: scope === 'all' }" @click="scope = 'all'">All</button><button :class="{ active: scope === 'past_exam' }" @click="scope = 'past_exam'">Past exams</button><button :class="{ active: scope === 'mock_exam' }" @click="scope = 'mock_exam'">Mock exams</button></div>
        <div class="heat-legend"><i class="status-unattempted" /><span>NOT STARTED</span><i class="status-progress" /><span>IN PROGRESS</span><i class="status-mastered" /><span>MASTERED</span><i class="status-review" /><span>REVIEW</span></div>
      </div>
    </header>
    <p v-if="error" class="error-state">{{ error }}</p>
    <div v-else-if="loading" class="question-skeleton">BUILDING HEATMAP…</div>
    <template v-else-if="data">
      <div class="heatmap-summary"><strong>{{ mode === 'topics' ? data.topic_count : data.question_count }}</strong><span>{{ mode === 'topics' ? 'indexed knowledge topics across all visible books' : scope === 'past_exam' ? 'verified official past-exam records' : scope === 'mock_exam' ? 'mock-exam records' : 'all practiceable records' }}</span></div>
      <section v-for="group in data.groups" :key="group.document_id" class="heatmap-group">
        <header><div><span>BOOK</span><h2>{{ group.document }}</h2></div><strong>{{ mode === 'topics' ? `${group.topics.length} topics` : `${group.questions.length} questions` }}</strong></header>
        <div v-if="mode === 'topics'" class="topic-heatmap">
          <button
            v-for="item in group.topics"
            :key="item.topic_id"
            :class="[`status-${item.state}`, `intensity-${item.intensity}`]"
            :aria-label="`${item.path}; ${item.coverage_percent}% covered; ${item.attempt_count} attempts`"
            :title="`${item.path} · ${item.attempted_question_count}/${item.question_count} covered · ${item.attempt_count} attempts${item.review_question_count ? ` · ${item.review_question_count} review` : ''}`"
            @click="openTopic(group.document_id, item.topic_id)"
          ><span>{{ item.topic }}</span></button>
        </div>
        <div v-else class="question-heatmap">
          <button v-for="item in group.questions" :key="item.uuid" :class="`status-${item.state}`" :aria-label="`${item.label}; ${item.state}; ${item.attempt_count} attempts`" :title="`${item.label} · ${item.topic} · ${item.state} · ${item.attempt_count} attempts`" @click="router.push(`/practice/${item.uuid}`)"><span>{{ item.year }}</span></button>
        </div>
      </section>
    </template>
  </section>
</template>
