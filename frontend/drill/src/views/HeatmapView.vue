<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../lib/api'

interface HeatmapQuestion {
  uuid: string
  order: number
  label: string
  topic: string
  year: number | null
  variant: string
  attempt_count: number
  latest_result: string | null
}

interface HeatmapPayload {
  question_count: number
  groups: Array<{ document_id: number; document: string; questions: HeatmapQuestion[] }>
}

const router = useRouter()
const data = ref<HeatmapPayload | null>(null)
const loading = ref(true)
const error = ref('')

function level(count: number) {
  return Math.min(4, count)
}

onMounted(async () => {
  try {
    data.value = await api('/api/drill/heatmap/')
  } catch (reason) {
    error.value = (reason as Error).message
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <section class="page heatmap-page">
    <header class="page-header">
      <div><span class="eyebrow">PAST PAPER COVERAGE</span><h1>A map of what you have touched.</h1><p>Empty means never attempted. Deeper color means more repetitions.</p></div>
      <div class="heat-legend"><span>NEVER</span><i v-for="levelValue in [0, 1, 2, 3, 4]" :key="levelValue" :class="`level-${levelValue}`" /><span>4+</span></div>
    </header>
    <p v-if="error" class="error-state">{{ error }}</p>
    <div v-else-if="loading" class="question-skeleton">BUILDING HEATMAP…</div>
    <template v-else-if="data">
      <div class="heatmap-summary"><strong>{{ data.question_count }}</strong><span>identified past-paper questions</span></div>
      <section v-for="group in data.groups" :key="group.document_id" class="heatmap-group">
        <header><div><span>QUESTION SET</span><h2>{{ group.document }}</h2></div><strong>{{ group.questions.length }}</strong></header>
        <div class="question-heatmap">
          <button v-for="item in group.questions" :key="item.uuid" :class="`level-${level(item.attempt_count)}`" :aria-label="`${item.label}; ${item.attempt_count} attempts`" :title="`${item.label} · ${item.topic} · ${item.attempt_count} attempts`" @click="router.push(`/practice/${item.uuid}`)"><span>{{ item.year }}</span></button>
        </div>
      </section>
    </template>
  </section>
</template>

