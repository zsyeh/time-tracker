<script setup lang="ts">
import { uiText } from '../lib/uiText'
import { onMounted, ref } from 'vue'
import { api } from '../lib/api'
import MarkdownAnswer from '../components/MarkdownAnswer.vue'
import PaperQuestionContent from '../components/PaperQuestionContent.vue'
import type { ExamPaper, ExamPaperItem, PaperItemResult } from '../types'
import { createAndCopyShare } from '../lib/share'
import { withWorkspacePrefix } from '../lib/runtimePath'

const props = defineProps<{ uuid: string }>()
const paper = ref<ExamPaper | null>(null)
const error = ref('')
const shareState = ref<'idle' | 'sharing' | 'copied'>('idle')

async function sharePaper() {
  if (shareState.value === 'sharing') return
  shareState.value = 'sharing'
  try {
    await createAndCopyShare(`/api/drill/papers/${props.uuid}/share/`)
    shareState.value = 'copied'
    window.setTimeout(() => { shareState.value = 'idle' }, 2500)
  } catch (reason) {
    shareState.value = 'idle'
    error.value = (reason as Error).message
  }
}

async function mark(item: ExamPaperItem, result: PaperItemResult) {
  item.result = result
  await api(`/api/drill/papers/${props.uuid}/items/${item.position}/`, {
    method: 'PATCH', body: JSON.stringify({ result }),
  })
}

onMounted(async () => {
  try { paper.value = await api<ExamPaper>(`/api/drill/papers/${props.uuid}/review/`) }
  catch (reason) { error.value = (reason as Error).message }
})
</script>

<template>
  <section class="page paper-review-page">
    <header class="page-header"><div><h1>{{ paper?.title || 'Paper review' }}</h1><p>Compare your work with the source answer and update the learning signal.</p></div><div class="paper-header-actions"><button type="button" :disabled="shareState === 'sharing'" @click="sharePaper">{{ shareState === 'sharing' ? 'Creating…' : shareState === 'copied' ? uiText("Link copied ✓") : 'Share paper + answers' }}</button><a :href="`/api/drill/papers/${uuid}/pdf/questions/`">Question PDF</a><a :href="`/api/drill/papers/${uuid}/pdf/solutions/`">Solution PDF</a><RouterLink :to="`/papers/${uuid}`">Exam view</RouterLink></div></header>
    <p v-if="error" class="error-state">{{ uiText(error) }}</p>
    <article v-for="item in paper?.items" :key="item.position" class="paper-review-item">
      <header><span>{{ item.position }}</span><div><strong>{{ item.question.display_label }}</strong><small>{{ item.question.document }} · {{ item.question.topic }}</small></div><em>{{ item.score }} pts</em></header>
      <PaperQuestionContent :question="item.question" />
      <section class="paper-your-answer"><span>Your answer</span><p>{{ item.user_answer || 'No answer recorded.' }}</p></section>
      <section class="paper-solution"><span>Source answer / explanation</span><MarkdownAnswer v-if="item.question.answer_markdown" :source="item.question.answer_markdown" /><div v-if="item.question.answer_assets?.length" class="paper-question-assets"><img v-for="asset in item.question.answer_assets" :key="asset.id" :src="withWorkspacePrefix(asset.url)" :width="asset.width" :height="asset.height" loading="lazy" decoding="async" alt="Answer" /></div><p v-if="!item.question.answer_markdown && !item.question.answer_assets?.length">No source answer is currently available.</p></section>
      <footer><span>Current: {{ item.question.mastery_state }}</span><div><button :class="{ selected: item.result === 'correct' }" @click="mark(item, 'correct')">Correct / mastered</button><button :class="{ selected: item.result === 'review' || item.result === 'incorrect' }" @click="mark(item, 'review')">{{ uiText("Needs review") }}</button></div></footer>
    </article>
  </section>
</template>


<style scoped>
.paper-header-actions a { color: var(--text-secondary); text-decoration: none; font-size: 12px; }
.paper-header-actions a:hover { color: var(--text-primary); }
.paper-header-actions a, .paper-header-actions button { padding: 6px 8px; border:0; border-radius: var(--radius-sm); color: var(--text-secondary); background: transparent; text-decoration: none; font-size: 12px; cursor: pointer; }
.paper-header-actions a:hover, .paper-header-actions button:hover { border-color: var(--border-default); color: var(--text-primary); background: var(--bg-surface-hover); }
.paper-your-answer > span, .paper-solution > span { color: var(--text-tertiary); font-size: 12px; text-transform: uppercase; }
.paper-review-item footer button { padding: 7px 10px; border:0; border-radius: var(--radius-sm); color: var(--text-secondary); background: transparent; cursor: pointer; }
.paper-header-actions { display: flex; gap: 5px; }
.paper-review-item { margin-bottom: 14px; padding: 16px; border:0; border-top:1px solid var(--border-subtle); border-radius:0; background:transparent; }
.paper-review-item > header { padding-bottom: 10px; border-bottom: 1px solid var(--border-subtle); display: grid; grid-template-columns: 28px 1fr auto; gap: 10px; align-items: center; }
.paper-review-item > header > span { color: var(--text-tertiary); font: 12px ui-monospace, monospace; }
.paper-review-item > header > div { display: grid; gap: 3px; }
.paper-review-item > header strong { font-size: 12px; }
.paper-review-item > header small, .paper-review-item > header em { color: var(--text-tertiary); font-size: 12px; font-style: normal; }
.paper-your-answer, .paper-solution { margin-top: 10px; padding: 12px; border-left:0; background:var(--surface-subtle); border-radius:6px; }
.paper-your-answer p, .paper-solution > p { color: var(--text-secondary); font-size: 12px; white-space: pre-wrap; }
.paper-review-item > footer { margin-top: 12px; padding-top: 10px; border-top: 1px solid var(--border-subtle); display: flex; align-items: center; justify-content: space-between; }
.paper-review-item > footer > span { color: var(--text-tertiary); font-size: 12px; }
.paper-review-item > footer > div { display: flex; gap: 5px; }
.paper-review-item footer button.selected { border-color:transparent; color:var(--text-primary); background:var(--surface-selected); }
@media (max-width: 700px) {
.paper-review-item > footer { align-items: stretch; flex-direction: column; }
.paper-header-actions { width: 100%; flex-wrap: wrap; }
}
.paper-review-item { padding:16px 0; } .paper-review-item > header strong { font-size:14px; } .paper-review-item footer button,.paper-header-actions a,.paper-header-actions button { min-height:44px; font-size:13px; } .paper-header-actions { flex-wrap:wrap; } .paper-review-item footer button { border:0; background:var(--surface-subtle); } .paper-your-answer p,.paper-solution > p { font-size:14px; }
</style>
