<script setup lang="ts">
import { uiText } from '../lib/uiText'
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../lib/api'
import PaperQuestionContent from '../components/PaperQuestionContent.vue'
import type { ExamPaper, PaperItemResult } from '../types'
import { createAndCopyShare } from '../lib/share'

const props = defineProps<{ uuid: string }>()
const router = useRouter()
const paper = ref<ExamPaper | null>(null)
const index = ref(0)
const error = ref('')
const now = ref(Date.now())
const shareState = ref<'idle' | 'sharing' | 'copied'>('idle')
let timer = 0
const item = computed(() => paper.value?.items[index.value] || null)
const remaining = computed(() => {
  if (!paper.value?.started_at) return paper.value?.duration_minutes || 0
  const elapsed = Math.floor((now.value - new Date(paper.value.started_at).getTime()) / 60000)
  return Math.max(0, paper.value.duration_minutes - elapsed)
})

async function patch(url: string, body: unknown) {
  return api(url, { method: 'PATCH', body: JSON.stringify(body) })
}

async function save(result?: PaperItemResult) {
  if (!item.value) return
  if (result) item.value.result = result
  await patch(`/api/drill/papers/${props.uuid}/items/${item.value.position}/`, {
    user_answer: item.value.user_answer,
    result: item.value.result,
  })
}

async function complete() {
  await save()
  await patch(`/api/drill/papers/${props.uuid}/`, { action: 'complete' })
  await router.push(`/papers/${props.uuid}/review`)
}

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

onMounted(async () => {
  try {
    paper.value = await api<ExamPaper>(`/api/drill/papers/${props.uuid}/`)
    if (paper.value.status === 'generated') {
      paper.value = await patch(`/api/drill/papers/${props.uuid}/`, { action: 'start' }) as ExamPaper
    }
    timer = window.setInterval(() => { now.value = Date.now() }, 30000)
  } catch (reason) { error.value = (reason as Error).message }
})
onUnmounted(() => window.clearInterval(timer))
</script>

<template>
  <section class="page paper-exam-page">
    <header v-if="paper" class="paper-exam-header"><RouterLink to="/papers">← Papers</RouterLink><div class="paper-exam-title"><strong>{{ paper.title }}</strong><small>{{ index + 1 }} / {{ paper.items.length }}</small></div><div class="paper-exam-actions"><button type="button" :disabled="shareState === 'sharing'" @click="sharePaper">{{ shareState === 'sharing' ? 'Creating…' : shareState === 'copied' ? uiText("Link copied ✓") : 'Share + answers' }}</button><span>{{ remaining }} min left</span></div></header>
    <p v-if="error" class="error-state">{{ uiText(error) }}</p>
    <template v-if="paper && item">
      <div class="paper-question-shell">
        <header><span>{{ uiText("Question") }} {{ item.position }}</span><span>{{ item.question.question_type.replace('_', ' ') }} · {{ item.score }} pts</span></header>
        <PaperQuestionContent :question="item.question" />
        <label class="paper-answer-field"><span>Your answer / working</span><textarea v-model="item.user_answer" rows="8" placeholder="Write your answer or working notes here…" @blur="save()" /></label>
      </div>
      <footer class="paper-exam-footer">
        <button type="button" :disabled="index === 0" @click="index--">{{ uiText("← Previous") }}</button>
        <div class="paper-position-dots"><button v-for="(entry, itemIndex) in paper.items" :key="entry.position" :class="{ active: itemIndex === index, answered: entry.user_answer || entry.result !== 'unanswered' }" :aria-label="`Question ${entry.position}${entry.user_answer || entry.result !== 'unanswered' ? ' · answered' : ''}`" :aria-current="itemIndex === index ? 'step' : undefined" @click="index = itemIndex">{{ entry.position }}<span v-if="entry.user_answer || entry.result !== 'unanswered'" aria-hidden="true">✓</span></button></div>
        <button v-if="index < paper.items.length - 1" type="button" @click="save(); index++">{{ uiText("Next →") }}</button>
        <button v-else class="primary-action" type="button" @click="complete">Finish</button>
      </footer>
    </template>
  </section>
</template>


<style scoped>
.paper-exam-header { min-height: 48px; border-bottom: 1px solid var(--border-subtle); display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; gap: 18px; }
.paper-exam-header > a { color: var(--text-secondary); text-decoration: none; font-size: 12px; }
.paper-exam-title { text-align: center; display: grid; gap: 2px; }
.paper-exam-header strong { font-size: 12px; }
.paper-exam-header small, .paper-exam-actions span { color: var(--text-tertiary); font-size: 12px; }
.paper-exam-actions { display: flex; justify-content: flex-end; align-items: center; gap: 8px; }
.paper-exam-actions span { font-family: ui-monospace, monospace; }
.paper-exam-actions button { padding: 5px 7px; border:0; border-radius:var(--radius-control); color: var(--text-secondary); background: transparent; font-size: 12px; cursor: pointer; }
.paper-exam-actions button:hover { border-color: var(--border-default); color: var(--text-primary); background: var(--bg-surface-hover); }
.paper-question-shell { width: min(100%, 900px); min-height: 620px; margin: 0 auto; padding: 26px 0 90px; }
.paper-question-shell > header { padding-bottom: 12px; border-bottom: 1px solid var(--border-subtle); color: var(--text-tertiary); display: flex; justify-content: space-between; font-size: 12px; }
.paper-answer-field { display: grid; gap: 7px; }
.paper-answer-field > span { color: var(--text-tertiary); font-size: 12px; text-transform: uppercase; }
.paper-answer-field textarea { width: 100%; padding: 12px; border:0; border-radius:var(--radius-control); color: var(--text-primary); background: var(--bg-sidebar); resize: vertical; }
.paper-exam-footer { position: sticky; bottom: 0; min-height: 54px; padding: 8px 10px; border:0; border-top:1px solid var(--border-subtle); border-radius:0; background: var(--bg-elevated); display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 16px; }
.paper-exam-footer > button { padding: 7px 10px; border:0; border-radius:var(--radius-control); color: var(--text-secondary); background: transparent; cursor: pointer; }
.paper-exam-footer > button:disabled { opacity: .35; cursor: default; }
.paper-position-dots { display: flex; justify-content: center; flex-wrap: wrap; gap: 5px; }
.paper-position-dots button { min-width:24px; height:28px; padding:0 4px; color:var(--text-primary); font-size:12px; border: 0; border-radius:4px; background:var(--surface-subtle); cursor: pointer; }
.paper-position-dots button.answered { background:var(--surface-hover); color:var(--text-primary); }
.paper-position-dots button.active { background:var(--surface-selected); box-shadow:inset 0 0 0 1px var(--text-primary); }
@media (max-width: 700px) {
.paper-exam-header { grid-template-columns: 1fr auto; }
.paper-exam-title { display: none; }
.paper-exam-footer { grid-template-columns: auto 1fr auto; gap: 8px; }
.paper-position-dots { max-height:88px; overflow:auto; }
}
.paper-exam-actions button,.paper-exam-footer > button { min-height:44px; padding:8px 12px; font-size:13px; } .paper-exam-footer { padding-bottom:max(8px,env(safe-area-inset-bottom)); } .paper-answer-field textarea { font-size:16px; border:1px solid var(--border-control); } @media(pointer:coarse) { .paper-position-dots button { min-width:32px; height:32px; } }
</style>
