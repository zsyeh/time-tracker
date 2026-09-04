<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, post } from '../lib/api'
import type { ExamBlueprint, ExamPaper } from '../types'

const router = useRouter()
const blueprints = ref<ExamBlueprint[]>([])
const selected = ref('')
const includeMastered = ref(false)
const loading = ref(false)
const error = ref('')

async function generate() {
  if (!selected.value) return
  loading.value = true
  error.value = ''
  try {
    const paper = await post<ExamPaper>('/api/drill/papers/', {
      blueprint: selected.value,
      include_mastered: includeMastered.value,
    })
    await router.push(`/papers/${paper.uuid}`)
  } catch (reason) {
    error.value = (reason as Error).message
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    blueprints.value = (await api<{ results: ExamBlueprint[] }>('/api/drill/papers/blueprints/')).results
    selected.value = blueprints.value.find((item) => item.mode === 'standard')?.code || blueprints.value[0]?.code || ''
  } catch (reason) {
    error.value = (reason as Error).message
  }
})
</script>

<template>
  <section class="page paper-new-page">
    <header class="page-header"><div><span class="eyebrow">SMART GENERATOR</span><h1>Build a Math II paper</h1><p>Choose one mode. The system handles type counts, coverage and recent work.</p></div><RouterLink class="quiet-link" to="/papers">History</RouterLink></header>
    <div class="blueprint-grid">
      <button v-for="blueprint in blueprints" :key="blueprint.code" type="button" :class="{ selected: selected === blueprint.code }" @click="selected = blueprint.code">
        <span>{{ blueprint.mode }}</span><h2>{{ blueprint.title }}</h2>
        <p>{{ blueprint.duration_minutes }} min · {{ blueprint.total_score }} points · {{ blueprint.question_count }} questions</p>
        <ul><li v-for="section in blueprint.sections" :key="`${blueprint.code}-${section.title}`">{{ section.question_count }} {{ section.question_type.replace('_', ' ') }}</li></ul>
      </button>
    </div>
    <div class="paper-generate-bar">
      <label><input v-model="includeMastered" type="checkbox" /> Allow mastered questions</label>
      <button class="primary-action" type="button" :disabled="loading || !selected" @click="generate">{{ loading ? 'Generating…' : 'Generate and start' }} <b>→</b></button>
    </div>
    <p v-if="error" class="error-state">{{ error }}</p>
  </section>
</template>
