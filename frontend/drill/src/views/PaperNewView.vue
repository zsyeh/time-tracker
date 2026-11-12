<script setup lang="ts">
import { uiText } from '../lib/uiText'
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
    <header class="page-header"><div><h1>Build a Math II paper</h1><p>Choose one mode. The system handles type counts, coverage and recent work.</p></div><RouterLink class="quiet-link" to="/papers">History</RouterLink></header>
    <div class="blueprint-grid">
      <button v-for="blueprint in blueprints" :key="blueprint.code" type="button" :class="{ selected: selected === blueprint.code }" :aria-pressed="selected === blueprint.code" @click="selected = blueprint.code">
        <span>{{ blueprint.mode }}</span><h2>{{ blueprint.title }}</h2>
        <p>{{ blueprint.duration_minutes }} min · {{ blueprint.total_score }} points · {{ blueprint.question_count }} {{ uiText("questions") }}</p>
        <ul><li v-for="section in blueprint.sections" :key="`${blueprint.code}-${section.title}`">{{ section.question_count }} {{ section.question_type.replace('_', ' ') }}</li></ul>
      </button>
    </div>
    <div class="paper-generate-bar">
      <label><input v-model="includeMastered" type="checkbox" /> Allow mastered questions</label>
      <button class="primary-action" type="button" :disabled="loading || !selected" @click="generate">{{ loading ? uiText("Generating…") : 'Generate and start' }} <b>→</b></button>
    </div>
    <p v-if="error" class="error-state">{{ uiText(error) }}</p>
  </section>
</template>


<style scoped>
.blueprint-grid { display: grid; grid-template-columns: repeat(3, 1fr); border:0; border-radius:0; background:transparent; gap:12px; }
.blueprint-grid > button { min-height:180px; padding:16px; border:0; border-radius:8px; color: var(--text-primary); background: transparent; text-align: left; cursor: pointer; }
.blueprint-grid > button:first-child { border-left: 0; }
.blueprint-grid > button:hover { background: var(--bg-surface-hover); }
.blueprint-grid > button.selected { box-shadow:none; background:var(--surface-selected); }
.blueprint-grid span { color: var(--text-tertiary); font-size: 12px; text-transform: uppercase; }
.blueprint-grid h2 { margin: 9px 0 5px; font-size: 14px; }
.blueprint-grid p, .blueprint-grid li { color: var(--text-secondary); font-size: 12px; line-height: 1.6; }
.blueprint-grid ul { margin: 12px 0 0; padding:12px 0 0; list-style:none; border-top: 1px solid var(--border-subtle); }
.paper-generate-bar { margin-top: 12px; padding: 12px 14px; border-top: 1px solid var(--border-subtle); display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.paper-generate-bar label { color: var(--text-secondary); font-size: 12px; }
@media (max-width: 700px) {
.blueprint-grid { grid-template-columns: 1fr; }
.blueprint-grid > button { min-height: 0; border-top:0; border-left:0; }
.blueprint-grid > button:first-child { border-top: 0; }
.paper-generate-bar { align-items: stretch; flex-direction: column; }
}
.paper-generate-bar label { display:flex; align-items:center; gap:8px; min-height:44px; font-size:14px; } .blueprint-grid > button { position:relative; } .blueprint-grid > button.selected::after { content:"✓"; position:absolute; top:12px; right:12px; color:var(--text-primary); }
</style>
