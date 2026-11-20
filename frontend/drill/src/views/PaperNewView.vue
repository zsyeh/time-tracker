<script setup lang="ts">
import { uiText } from '../lib/uiText'
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, post } from '../lib/api'
import type { ExamBlueprint, ExamPaper } from '../types'

const router = useRouter()
const blueprints = ref<ExamBlueprint[]>([])
const selected = ref('')
const includeMastered = ref(true)
const excludeReview = ref(false)
const cooldownDays = ref(0)
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
      exclude_review: excludeReview.value,
      cooldown_days: cooldownDays.value,
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
    <header class="page-header"><div><h1>数学二 · 专注训练</h1><p>按高数 / 线代固定配额组卷，全部使用题干和答案贴图。可随时看答案或进入标准练习。</p></div><RouterLink class="quiet-link" to="/papers">训练题单</RouterLink></header>
    <div class="blueprint-grid">
      <button v-for="blueprint in blueprints" :key="blueprint.code" type="button" :class="{ selected: selected === blueprint.code }" :aria-pressed="selected === blueprint.code" @click="selected = blueprint.code">
        <span>{{ blueprint.mode === 'standard' ? '22 题 · 标准训练' : '33 题 · 强化训练' }}</span><h2>{{ blueprint.title }}</h2>
        <p>{{ blueprint.duration_minutes }} 分钟 · {{ blueprint.total_score }} 分 · {{ blueprint.question_count }} {{ uiText("questions") }}</p>
        <ul><li v-for="section in blueprint.sections" :key="`${blueprint.code}-${section.title}`">{{ section.title }} · {{ section.question_count }} 题</li></ul>
      </button>
    </div>
    <div class="paper-generate-bar">
      <div class="generation-filters">
        <label><input :checked="!includeMastered" type="checkbox" @change="includeMastered = !($event.target as HTMLInputElement).checked" /> 排除已掌握题</label>
        <label><input v-model="excludeReview" type="checkbox" /> 排除待复习题</label>
        <label>排除最近 <select v-model.number="cooldownDays"><option :value="0">不强制排除</option><option :value="1">1 天</option><option :value="3">3 天</option><option :value="7">7 天</option><option :value="14">14 天</option></select> 做过的题</label>
      </div>
      <button class="primary-action" type="button" :disabled="loading || !selected" @click="generate">{{ loading ? uiText("Generating…") : '生成固定题单' }} <b>→</b></button>
    </div>
    <p class="generation-hint">优先分散知识点、减少近期重复；勾选的排除条件不会自动放宽。题库暂无可靠难度标签，不承诺精确模拟真题难度。</p>
    <p v-if="error" class="error-state">{{ uiText(error) }}</p>
  </section>
</template>


<style scoped>
.generation-filters { display:flex; flex-wrap:wrap; gap:8px 16px; } .generation-hint { color:var(--text-secondary); font-size:13px; line-height:1.6; }
.blueprint-grid { display: grid; grid-template-columns: repeat(2, 1fr); border:0; border-radius:0; background:transparent; gap:12px; }
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
