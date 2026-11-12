<script setup lang="ts">
import { computed } from 'vue'
import type { ErrorCode } from '../types'
import { uiText } from '../lib/uiText'
import { typeText } from '../lib/examTypes'

const props = withDefaults(defineProps<{
  modelValue: ErrorCode[]
  primary: ErrorCode | null
  options: Array<{ code: ErrorCode; label: string; group: string }>
  disabled?: boolean
  compact?: boolean
}>(), { disabled: false, compact: false })
const emit = defineEmits<{ toggle: [code: ErrorCode] }>()
const groups = computed(() => props.compact ? [{ id: 'all', label: typeText('知识 · 方法 · 执行 · 理解', 'Knowledge · Method · Execution · Understanding'), items: props.options }] : [
  { id: 'A', label: typeText('知识', 'Knowledge'), items: props.options.filter(item => item.group === 'A') },
  { id: 'B', label: typeText('方法', 'Method'), items: props.options.filter(item => item.group === 'B') },
  { id: 'C', label: typeText('执行', 'Execution'), items: props.options.filter(item => item.group === 'C') },
  { id: 'D', label: typeText('理解', 'Understanding'), items: props.options.filter(item => item.group === 'D') },
])
</script>

<template>
  <div class="diagnosis-selector" :class="{ compact }">
    <div class="diagnosis-selection-groups">
      <fieldset v-for="group in groups" :key="group.id" :disabled="disabled">
        <legend>{{ group.label }}</legend>
        <label v-for="item in group.items" :key="item.code" class="diagnosis-selection-row" :class="{ selected: modelValue.includes(item.code) }">
          <input type="checkbox" :value="item.code" :checked="modelValue.includes(item.code)" :aria-label="`${item.code} · ${uiText(item.label)}${primary === item.code ? ` · ${uiText('主要原因')}` : ''}`" @change="emit('toggle', item.code)">
          <span class="diagnosis-code" :class="{ primary: primary === item.code }" aria-hidden="true">{{ item.code }}</span>
          <span class="diagnosis-label">{{ uiText(item.label) }}</span>
          <small v-if="primary === item.code && !compact" class="diagnosis-primary">{{ uiText('主要原因') }}</small>
          <svg class="diagnosis-check" :class="{ checked: modelValue.includes(item.code) }" width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="m4 10 4 4 8-8" /></svg>
        </label>
      </fieldset>
    </div>
  </div>
</template>

<style scoped>
.diagnosis-selector { container-type: inline-size; min-width: 0; }
.diagnosis-selection-groups { display: grid; gap: 12px; }
fieldset { min-width: 0; margin: 0; padding: 0; border: 0; }
legend { margin-bottom: 4px; padding: 0 8px; color: var(--text-secondary); font-size: 12px; font-weight: 600; }
.diagnosis-selection-row { position: relative; display: flex; align-items: center; gap: 8px; min-width: 0; min-height: 44px; padding: 4px 8px; border-radius: 6px; color: var(--text-primary); cursor: pointer; }
.diagnosis-selection-row:hover { background: var(--surface-hover, var(--bg-hover)); }
.diagnosis-selection-row.selected { background: var(--surface-selected, var(--bg-surface-active)); }
.diagnosis-selection-row:focus-within { outline: 2px solid var(--accent-ink, var(--accent)); outline-offset: 2px; }
.diagnosis-selection-row input { position: absolute; width: 1px; height: 1px; overflow: hidden; opacity: 0; }
.diagnosis-code { flex: none; width: 28px; color: var(--text-secondary); font-size: 12px; font-variant-numeric: tabular-nums; }
.diagnosis-label { flex: 1; min-width: 0; font-size: 14px; line-height: 1.4; overflow-wrap: anywhere; }
.diagnosis-primary { flex: none; color: var(--text-secondary); font-size: 12px; }
.diagnosis-check { flex: none; opacity: 0; }
.diagnosis-check.checked { opacity: 1; }
fieldset:disabled .diagnosis-selection-row { cursor: default; opacity: .55; }
.compact .diagnosis-selection-groups { grid-template-columns: minmax(0, 1fr); gap: 4px; }
.compact fieldset { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 4px; }
.compact legend { margin-bottom: 0; font-size: 12px; }
.compact .diagnosis-selection-row { gap: 4px; padding: 2px 4px; }
.compact .diagnosis-code { width: 20px; }
.diagnosis-code.primary { font-weight: 750; color: var(--text-primary); }
@container (min-width: 360px) { .compact fieldset { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@container (min-width: 600px) { .compact fieldset { grid-template-columns: repeat(4, minmax(0, 1fr)); } }
@container (max-width: 279px) { .compact fieldset { grid-template-columns: minmax(0, 1fr); } }
@container (min-width: 600px) { .diagnosis-selection-groups { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; } }
</style>
