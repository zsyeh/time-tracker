<script setup lang="ts">
import { ref } from 'vue'
import { api } from '../lib/api'
import type { QuestionDetail } from '../types'
import MarkdownAnswer from './MarkdownAnswer.vue'

const props = defineProps<{ uuid: string }>()
const answer = ref<QuestionDetail | null>(null)
const loading = ref(false)
const error = ref('')

async function load(event: Event) {
  if (!(event.currentTarget as HTMLDetailsElement).open || answer.value || loading.value) return
  loading.value = true
  error.value = ''
  try {
    answer.value = await api<QuestionDetail>(`/api/drill/questions/${props.uuid}/`)
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '加载失败，请重新展开重试。'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <details class="original-answer" @toggle="load">
    <summary>查看完整版答案（原始解析全部保留）</summary>
    <p v-if="loading" role="status">正在加载完整版答案…</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <div v-if="answer" class="original-answer-pages">
      <img v-for="asset in answer.answer_assets" :key="asset.id" :src="asset.url" :width="asset.width" :height="asset.height" alt="完整版答案页面" loading="lazy" decoding="async" />
      <MarkdownAnswer v-if="answer.answer_markdown" :source="answer.answer_markdown" />
    </div>
  </details>
</template>

<style scoped>
.original-answer { margin-top: 12px; padding: 12px; border: 1px solid #59616e; border-radius: 8px; }
summary { cursor: pointer; font-size: 13px; }
.original-answer-pages { margin-top: 12px; }
img { display: block; width: 100%; height: auto; margin-bottom: 12px; background: white; }
</style>
