<script setup lang="ts">
import { uiText } from '../lib/uiText'
import { computed, ref } from 'vue'
import { api } from '../lib/api'
import { runtimeWorkspace } from '../lib/runtimePath'
import { typeLabel, typeText } from '../lib/examTypes'
import type { QuestionDetail } from '../types'
import ExamTypeBadge from './ExamTypeBadge.vue'

const props = defineProps<{ question: QuestionDetail }>()
const emit = defineEmits<{ saved: [patch: Partial<QuestionDetail>] }>()
const open = ref(false)
const busy = ref(false)
const error = ref('')
const selected = ref('unknown')
const revision = ref<string | null>(null)
const options = computed(() => runtimeWorkspace === 'ei'
  ? ['choice', 'fill', 'judgment', 'short_answer', 'large', 'unknown']
  : ['choice', 'fill', 'large'])
const url = () => `/api/drill/questions/${props.question.uuid}/exam-type/`
async function toggle() {
  if (busy.value) return
  if (open.value) { open.value = false; return }
  open.value = true
  busy.value = true
  error.value = ''
  try {
    const result = await api<Partial<QuestionDetail>>(url())
    selected.value = result.question_type || 'unknown'
    revision.value = result.classification?.updated_at || null
  } catch {
    error.value = typeText('读取失败，请关闭重试', 'Could not load. Close and retry.')
  } finally { busy.value = false }
}
async function save(label: string) {
  if (busy.value || error.value) return
  busy.value = true
  error.value = ''
  try {
    const result = await api<Partial<QuestionDetail>>(url(), {
      method: 'PATCH', body: JSON.stringify({ question_type: label, expected_updated_at: revision.value }),
    })
    emit('saved', result)
    open.value = false
  } catch {
    error.value = typeText('未保存，请关闭后重试', 'Not saved. Close and retry.')
  } finally { busy.value = false }
}
</script>

<template>
  <span class="format-editor" @keydown.esc="open = false">
    <button class="format-trigger" type="button" :aria-expanded="open" :title="typeText('编辑题型', 'Edit question format')" @click="toggle">
      <ExamTypeBadge :type="question.question_type" :group="question.type_group" />
    </button>
    <span v-if="open" class="format-picker" role="group" :aria-label="typeText('编辑题型', 'Edit question format')">
      <button v-for="item in options" :key="item" type="button" class="format-option"
        :aria-pressed="selected === item" :disabled="busy || !!error" @click="save(item)">{{ typeLabel(item) }}</button>
      <button type="button" :disabled="busy" :aria-label="typeText('关闭', 'Close')" @click="open = false">×</button>
      <small v-if="busy" role="status">{{ typeText('处理中…', 'Working…') }}</small>
      <small v-if="error" role="alert">{{ uiText(error) }}</small>
    </span>
  </span>
</template>

<style scoped>
.format-editor { position:relative; display:inline-flex; }
.format-trigger { padding:2px 4px; border:0; background:transparent; cursor:pointer; border-radius:4px; }
.format-trigger:focus-visible { outline:1px solid var(--accent); }
.format-picker { position:absolute; top:100%; left:0; z-index:20; display:flex; flex-wrap:wrap; align-items:center; gap:6px; width:max-content; max-width:240px; padding:7px; border:1px solid var(--border-default); border-radius:7px; background:var(--bg-elevated); box-shadow:0 3px 12px #0002; }
.format-picker button { border:0; background:transparent; color:var(--accent); font-size:12px; padding:3px; min-height:28px; cursor:pointer; }
.format-option[aria-pressed="true"] { background:var(--accent-muted); border-radius:4px; }
.format-picker button:disabled { opacity:.5; cursor:default; }
.format-picker small { flex-basis:100%; color:var(--text-secondary); font-size:11px; }
</style>
