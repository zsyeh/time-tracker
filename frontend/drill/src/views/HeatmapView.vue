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

interface HeatmapPayload {
  question_count: number
  groups: Array<{ document_id: number; document: string; questions: HeatmapQuestion[] }>
}

const router = useRouter()
const data = ref<HeatmapPayload | null>(null)
const loading = ref(true)
const error = ref('')
const scope = ref<'past_exam' | 'mock_exam' | 'all'>('past_exam')

async function load() {
  const requestedScope = scope.value
  const cached = cachedHeatmap<HeatmapPayload>(requestedScope)
  if (cached) data.value = cached
  loading.value = !cached
  error.value = ''
  try {
    const value = await api<HeatmapPayload>(`/api/drill/heatmap/?scope=${requestedScope}`)
    if (scope.value !== requestedScope) return
    data.value = value
    storeHeatmap(requestedScope, value)
  } catch (reason) {
    error.value = (reason as Error).message
  } finally {
    if (scope.value === requestedScope) loading.value = false
  }
}

watch(scope, load)
onMounted(load)
</script>

<template>
  <section class="page heatmap-page">
    <header class="page-header">
      <div><span class="eyebrow">VERIFIED PAST PAPERS</span><h1>A clear map of your current state.</h1><p>Switch between official exams, mock exams, and all practiceable questions. Frequency remains available in each cell tooltip.</p></div>
      <div class="heat-scope"><button :class="{ active: scope === 'past_exam' }" @click="scope = 'past_exam'">Past exams</button><button :class="{ active: scope === 'mock_exam' }" @click="scope = 'mock_exam'">Mock exams</button><button :class="{ active: scope === 'all' }" @click="scope = 'all'">All questions</button></div><div class="heat-legend"><i class="status-unattempted" /><span>NOT STARTED</span><i class="status-mastered" /><span>MASTERED</span><i class="status-review" /><span>REVIEW</span></div>
    </header>
    <p v-if="error" class="error-state">{{ error }}</p>
    <div v-else-if="loading" class="question-skeleton">BUILDING HEATMAP…</div>
    <template v-else-if="data">
      <div class="heatmap-summary"><strong>{{ data.question_count }}</strong><span>{{ scope === 'past_exam' ? 'verified official past-exam records' : scope === 'mock_exam' ? 'mock-exam records' : 'all practiceable records' }}</span></div>
      <section v-for="group in data.groups" :key="group.document_id" class="heatmap-group">
        <header><div><span>QUESTION SET</span><h2>{{ group.document }}</h2></div><strong>{{ group.questions.length }}</strong></header>
        <div class="question-heatmap">
          <button v-for="item in group.questions" :key="item.uuid" :class="`status-${item.state}`" :aria-label="`${item.label}; ${item.state}; ${item.attempt_count} attempts`" :title="`${item.label} · ${item.topic} · ${item.state} · ${item.attempt_count} attempts`" @click="router.push(`/practice/${item.uuid}`)"><span>{{ item.year }}</span></button>
        </div>
      </section>
    </template>
  </section>
</template>
