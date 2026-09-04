<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../lib/api'
import MarkdownAnswer from '../components/MarkdownAnswer.vue'
import PaperQuestionContent from '../components/PaperQuestionContent.vue'
import type { ExamPaper, ExamPaperItem, PaperItemResult } from '../types'

const props = defineProps<{ uuid: string }>()
const paper = ref<ExamPaper | null>(null)
const error = ref('')

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
    <header class="page-header"><div><span class="eyebrow">REVIEW</span><h1>{{ paper?.title || 'Paper review' }}</h1><p>Compare your work with the source answer and update the learning signal.</p></div><div class="paper-header-actions"><a :href="`/api/drill/papers/${uuid}/pdf/questions/`">Question PDF</a><a :href="`/api/drill/papers/${uuid}/pdf/solutions/`">Solution PDF</a><RouterLink :to="`/papers/${uuid}`">Exam view</RouterLink></div></header>
    <p v-if="error" class="error-state">{{ error }}</p>
    <article v-for="item in paper?.items" :key="item.position" class="paper-review-item">
      <header><span>{{ item.position }}</span><div><strong>{{ item.question.display_label }}</strong><small>{{ item.question.document }} · {{ item.question.topic }}</small></div><em>{{ item.score }} pts</em></header>
      <PaperQuestionContent :question="item.question" />
      <section class="paper-your-answer"><span>Your answer</span><p>{{ item.user_answer || 'No answer recorded.' }}</p></section>
      <section class="paper-solution"><span>Source answer / explanation</span><MarkdownAnswer v-if="item.question.answer_markdown" :source="item.question.answer_markdown" /><div v-if="item.question.answer_assets?.length" class="paper-question-assets"><img v-for="asset in item.question.answer_assets" :key="asset.id" :src="asset.url" :width="asset.width" :height="asset.height" loading="lazy" decoding="async" alt="Answer" /></div><p v-if="!item.question.answer_markdown && !item.question.answer_assets?.length">No source answer is currently available.</p></section>
      <footer><span>Current: {{ item.question.mastery_state }}</span><div><button :class="{ selected: item.result === 'correct' }" @click="mark(item, 'correct')">Correct / mastered</button><button :class="{ selected: item.result === 'review' || item.result === 'incorrect' }" @click="mark(item, 'review')">Needs review</button></div></footer>
    </article>
  </section>
</template>
