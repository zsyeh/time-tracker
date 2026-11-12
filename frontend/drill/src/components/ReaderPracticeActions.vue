<script setup lang="ts">
import { computed } from 'vue'
import { typeText } from '../lib/examTypes'
import { readerDestinationColour, type ReaderPracticeAction, type ReaderPracticeControls } from '../lib/readerPractice'
const props = defineProps<{ controls: ReaderPracticeControls }>()
const emit = defineEmits<{ action: [action: ReaderPracticeAction] }>()
const grey = 'var(--text-secondary)'
const green = 'var(--success, #64b781)'
const yellow = 'var(--warning, #d4a857)'
const destination = computed(() => props.controls.mode === 'unattempted' ? typeText('未做题', 'unattempted questions') : props.controls.mode === 'overdue' ? typeText('红色到期题', 'red overdue questions') : props.controls.mode === 'review' ? typeText('黄色复习题', 'yellow review questions') : typeText('顺序题', 'sequential questions'))
const navColour = computed(() => readerDestinationColour(props.controls.mode, grey))
const masterColour = computed(() => readerDestinationColour(props.controls.mode, green))
const reviewColour = computed(() => props.controls.mode === 'review' ? 'color-mix(in srgb, var(--warning, #d4a857) 58%, white)' : readerDestinationColour(props.controls.mode, yellow))
const masterLabel = computed(() => typeText('已掌握', 'Mastered') + (props.controls.masteredAutoNext ? ` · ${typeText('下一题', 'next')} · ${destination.value}` : ''))
const reviewLabel = computed(() => typeText('待复习', 'Needs review') + (props.controls.reviewAutoNext ? ` · ${typeText('下一题', 'next')} · ${destination.value}` : ''))
</script>

<template>
  <nav class="reader-practice-actions" :aria-label="typeText('全屏做题操作', 'Full-screen practice actions')" :data-mode="controls.mode">
    <button type="button" data-action="previous" :disabled="controls.busy || !controls.canPrevious" :title="`${typeText('上一题', 'Previous question')} · ${destination}`" :aria-label="`${typeText('上一题', 'Previous question')} · ${destination}`" @click="emit('action', 'previous')"><svg viewBox="0 0 24 24" fill="none" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 12H6" :stroke="grey"/><path d="m12 5-7 7 7 7" :stroke="navColour"/></svg></button>
    <button type="button" data-action="next" :disabled="controls.busy || !controls.canNext" :title="`${typeText('下一题', 'Next question')} · ${destination}`" :aria-label="`${typeText('下一题', 'Next question')} · ${destination}`" @click="emit('action', 'next')"><svg viewBox="0 0 24 24" fill="none" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 12h14" :stroke="grey"/><path d="m12 5 7 7-7 7" :stroke="navColour"/></svg></button>
    <button type="button" data-action="mastered" class="reader-mastered" :disabled="controls.busy" :aria-pressed="controls.state === 'mastered'" :title="masterLabel" :aria-label="masterLabel" @click="emit('action', 'mastered')"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path :d="controls.masteredAutoNext ? 'm3 9 4 4L15 5' : 'm4 12 5 5L20 6'" :stroke="green"/><path v-if="controls.masteredAutoNext" d="M12 19h9m-3-3 3 3-3 3" :stroke="masterColour"/></svg></button>
    <button type="button" data-action="review" class="reader-review" :disabled="controls.busy" :aria-pressed="controls.state === 'review'" :title="reviewLabel" :aria-label="reviewLabel" @click="emit('action', 'review')"><svg viewBox="0 0 24 24" fill="none" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle :cx="controls.reviewAutoNext ? 10 : 12" :cy="controls.reviewAutoNext ? 10 : 12" :r="controls.reviewAutoNext ? 7 : 8" :stroke="yellow"/><path :d="controls.reviewAutoNext ? 'M10 6v4l3 2' : 'M12 7v5l3 2'" :stroke="yellow"/><path v-if="controls.reviewAutoNext" d="M12 20h9m-3-3 3 3-3 3" :stroke="reviewColour"/></svg></button>
    <button type="button" data-action="answer" class="reader-answer" :disabled="controls.busy || !controls.canAnswer" :aria-pressed="!!controls.answerActive" :title="controls.answerActive ? typeText('返回题目', 'Back to question') : typeText('显示答案', 'Show answer')" :aria-label="controls.answerActive ? typeText('返回题目', 'Back to question') : typeText('显示答案', 'Show answer')" @click="emit('action', 'answer')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 5C9 3 5 3 3 4v15c3-1 6-1 9 1 3-2 6-2 9-1V4c-2-1-6-1-9 1v15"/><path d="m5 10 2 2 3-4m5 1h3m-3 4h3"/></svg></button>
  </nav>
</template>

<style scoped>
.reader-practice-actions { display: flex; flex: none; align-items: center; gap: 8px; }
.reader-practice-actions button { display: grid; place-items: center; flex: none; width: 32px; height: 32px; padding: 5px; border: 0; border-radius: 6px; color: var(--text-secondary); background: transparent; cursor: pointer; }
.reader-practice-actions svg { width: 20px; height: 20px; }
.reader-practice-actions button:hover:not(:disabled) { background: var(--surface-hover, var(--bg-sidebar)); }
.reader-practice-actions button:focus-visible { outline: 2px solid var(--accent-ink, var(--accent)); outline-offset: 2px; }
.reader-practice-actions button:disabled { opacity: .4; cursor: default; }
.reader-practice-actions button[aria-pressed="true"] { background: var(--surface-selected, var(--bg-surface-active)); }
.reader-practice-actions .reader-answer { color: var(--text-primary); }
@media (pointer: coarse) { .reader-practice-actions { gap: 4px; } .reader-practice-actions button { width: 44px; height: 44px; padding: 10px; } }
</style>
