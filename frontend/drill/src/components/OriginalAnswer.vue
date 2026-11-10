<script setup lang="ts">
import { uiText } from '../lib/uiText'
import { computed, ref } from 'vue'
import type { ReaderPracticeAction, ReaderPracticeControls } from '../lib/readerPractice'
import { api } from '../lib/api'
import type { QuestionDetail } from '../types'
import MarkdownAnswer from './MarkdownAnswer.vue'
import FullscreenReader from './FullscreenReader.vue'
import { typeText } from '../lib/examTypes'
import { withWorkspacePrefix } from '../lib/runtimePath'

const props = defineProps<{ uuid: string; controls?: ReaderPracticeControls; delegateFullscreen?: boolean }>()
const emit = defineEmits<{ opened: []; action: [action: ReaderPracticeAction]; fullscreen: [] }>()
const reader = ref<InstanceType<typeof FullscreenReader> | null>(null)
const answer = ref<QuestionDetail | null>(null)
const loading = ref(false)
const error = ref('')

async function ensureAnswer() {
  if (answer.value) return
  loading.value = true
  error.value = ''
  try {
    answer.value = await api<QuestionDetail>(`/api/drill/questions/${props.uuid}/`)
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : typeText('加载失败，请重新展开重试。', 'Failed to load. Expand again to retry.')
    throw reason
  } finally {
    loading.value = false
  }
}
async function load(event: Event) {
  if (!(event.currentTarget as HTMLDetailsElement).open || answer.value || loading.value) return
  emit('opened')
  try { await ensureAnswer() } catch { /* The error is displayed beside the answer. */ }
}
defineExpose({ readFullscreenAnswer: async () => { await ensureAnswer(); return answer.value! }, openFullscreen: () => reader.value?.open(), closeFullscreen: () => reader.value?.close(), isFullscreenOpen: computed(() => reader.value?.isOpen || false) })
</script>

<template>
  <details class="original-answer" @toggle="load">
    <summary><span>{{ uiText("查看完整版答案（原始解析全部保留）") }}</span><button v-if="delegateFullscreen" type="button" class="fullscreen-trigger inline-fullscreen-trigger" :title="typeText('完整答案全屏', 'Complete answers full screen')" :aria-label="typeText('完整答案全屏', 'Complete answers full screen')" @click.stop="emit('fullscreen')"><svg width="15" height="15" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M7 3H3v4m10-4h4v4M3 13v4h4m10-4v4h-4" /></svg></button><FullscreenReader v-else ref="reader" :controls="controls" @action="emit('action', $event)" :title="typeText('完整答案', 'Complete answers')" :images="(answer?.answer_assets || []).map(asset => ({ src: withWorkspacePrefix(asset.url), width: asset.width, height: asset.height }))" :markdown="answer?.answer_markdown" :prepare="ensureAnswer" @opened="emit('opened')" /></summary>
    <p v-if="loading" role="status">{{ uiText("正在加载完整版答案…") }}</p>
    <p v-if="error" role="alert">{{ uiText(error) }}</p>
    <div v-if="answer" class="original-answer-pages">
      <img v-for="asset in answer.answer_assets" :key="asset.id" :src="withWorkspacePrefix(asset.url)" :width="asset.width" :height="asset.height" :alt="uiText('完整版答案页面')" loading="lazy" decoding="async" />
      <MarkdownAnswer v-if="answer.answer_markdown" :source="answer.answer_markdown" />
    </div>
  </details>
</template>

<style scoped>
.original-answer { margin-top: 12px; padding: 12px; border: 1px solid #59616e; border-radius: 8px; }
summary { display: flex; align-items: center; justify-content: space-between; gap: 6px; cursor: pointer; font-size: 13px; }
.original-answer-pages { margin-top: 12px; }
img { display: block; width: 100%; height: auto; margin-bottom: 12px; background: white; }
</style>
