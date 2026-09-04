<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../lib/api'
import PaperQuestionContent from '../components/PaperQuestionContent.vue'
import type { ExamPaper, PaperItemResult } from '../types'

const props = defineProps<{ uuid: string }>()
const router = useRouter()
const paper = ref<ExamPaper | null>(null)
const index = ref(0)
const error = ref('')
const now = ref(Date.now())
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
    <header v-if="paper" class="paper-exam-header"><RouterLink to="/papers">← Papers</RouterLink><div><strong>{{ paper.title }}</strong><small>{{ index + 1 }} / {{ paper.items.length }}</small></div><span>{{ remaining }} min left</span></header>
    <p v-if="error" class="error-state">{{ error }}</p>
    <template v-if="paper && item">
      <div class="paper-question-shell">
        <header><span>Question {{ item.position }}</span><span>{{ item.question.question_type.replace('_', ' ') }} · {{ item.score }} pts</span></header>
        <PaperQuestionContent :question="item.question" />
        <label class="paper-answer-field"><span>Your answer / working</span><textarea v-model="item.user_answer" rows="8" placeholder="Write your answer or working notes here…" @blur="save()" /></label>
      </div>
      <footer class="paper-exam-footer">
        <button type="button" :disabled="index === 0" @click="index--">← Previous</button>
        <div class="paper-position-dots"><button v-for="(entry, itemIndex) in paper.items" :key="entry.position" :class="{ active: itemIndex === index, answered: entry.user_answer || entry.result !== 'unanswered' }" :aria-label="`Question ${entry.position}`" @click="index = itemIndex" /></div>
        <button v-if="index < paper.items.length - 1" type="button" @click="save(); index++">Next →</button>
        <button v-else class="primary-action" type="button" @click="complete">Finish</button>
      </footer>
    </template>
  </section>
</template>
