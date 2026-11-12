<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { typeText } from '../lib/examTypes'
const toolbar = ref<HTMLElement | null>(null)
function closeMenu(restoreFocus = false) {
  const menu = toolbar.value?.querySelector<HTMLDetailsElement>('details[open]')
  if (!menu) return
  menu.open = false
  if (restoreFocus) menu.querySelector('summary')?.focus()
}
function dismissOutside(event: PointerEvent) {
  if (event.target instanceof Node && !toolbar.value?.contains(event.target)) closeMenu()
}
function actionClicked(event: MouseEvent) {
  if (event.target instanceof Element && event.target.closest('.practice-more-menu button')) closeMenu()
}
onMounted(() => document.addEventListener('pointerdown', dismissOutside))
onBeforeUnmount(() => document.removeEventListener('pointerdown', dismissOutside))
</script>

<template>
  <div ref="toolbar" class="practice-action-toolbar unified-answer-actions" role="group" :aria-label="typeText('提交作答', 'Submit answer')" @keydown.esc.stop.prevent="closeMenu(true)" @click="actionClicked">
    <slot name="primary" />
    <slot name="secondary" />
    <slot name="more" />
  </div>
</template>

<style scoped>
.practice-action-toolbar { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(0, 1fr) auto; gap: 8px; min-width: 0; margin-top: 16px; }
.practice-action-toolbar :deep(button), .practice-action-toolbar :deep(summary) { min-width: 0; min-height: 44px; padding: 8px 12px; border: 0; border-radius: 6px; color: var(--text-primary); background: var(--surface-hover, var(--bg-sidebar)); font-size: 14px; font-weight: 550; cursor: pointer; }
.practice-action-toolbar :deep(button:hover:not(:disabled)), .practice-action-toolbar :deep(summary:hover) { background: var(--surface-selected, var(--bg-surface-active)); }
.practice-action-toolbar :deep(.primary-action) { color: var(--accent-on-solid, var(--text-primary)); background: var(--accent-solid, var(--accent)); font-weight: 650; }
.practice-action-toolbar :deep(.primary-action:hover:not(:disabled)) { background: var(--accent-solid, var(--accent)); filter: brightness(.94); }
.practice-action-toolbar :deep(.review.selected) { color: var(--status-review, var(--warning)); }
.practice-action-toolbar :deep(button:disabled) { cursor: default; opacity: .45; }
.practice-action-toolbar :deep(button:focus-visible), .practice-action-toolbar :deep(summary:focus-visible) { outline: 2px solid var(--accent-ink, var(--accent)); outline-offset: 2px; }
.practice-action-toolbar :deep(details) { position: relative; min-width: 0; }
.practice-action-toolbar :deep(summary) { display: grid; align-items: center; list-style: none; text-align: center; color: var(--text-secondary); background: transparent; }
.practice-action-toolbar :deep(summary::-webkit-details-marker) { display: none; }
.practice-action-toolbar :deep(.practice-more-menu) { display: grid; gap: 4px; position: absolute; bottom: calc(100% + 8px); right: 0; z-index: 30; width: 192px; max-width: calc(100vw - 32px); padding: 4px; border: 1px solid var(--border-subtle); border-radius: 8px; background: var(--surface-elevated, var(--bg-surface)); box-shadow: 0 8px 24px #0002; }
.practice-action-toolbar :deep(.practice-more-menu button) { text-align: left; background: transparent; }
.practice-action-toolbar :deep(.destructive-action) { color: var(--status-danger, var(--danger)); }
@media (max-width: 480px) { .practice-action-toolbar { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); } .practice-action-toolbar :deep(details) { grid-column: 1 / -1; } .practice-action-toolbar :deep(summary) { min-height: 36px; } }
</style>
