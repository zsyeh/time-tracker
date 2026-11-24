<script setup lang="ts">
import MarkdownAnswer from './MarkdownAnswer.vue'
defineEmits<{ rendered: [] }>()
withDefaults(defineProps<{ title: string; source: string; open?: boolean }>(), { open: true })
</script>
<template>
  <details class="markdown-section" :open="open">
    <summary>{{ title }}</summary>
    <MarkdownAnswer :source="source" @rendered="$emit('rendered')" />
  </details>
</template>
<style scoped>
.markdown-section { min-width:0; padding:16px 0; border-bottom:1px solid var(--border-subtle); }
summary { cursor:pointer; font-size:16px; font-weight:600; min-height:40px; }
:deep(.markdown-body) { overflow-wrap:anywhere; color:var(--text-primary); font-size:14px; }
</style>
