<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{ source: string }>()
const html = ref('')
const loading = ref(false)
let version = 0

watch(() => props.source, async (source) => {
  const current = ++version
  if (!source.trim()) { html.value = ''; return }
  loading.value = true
  try {
    const { renderMarkdown } = await import('../../../src/lib/markdown')
    if (current === version) html.value = renderMarkdown(source)
  } finally {
    if (current === version) loading.value = false
  }
}, { immediate: true })
</script>

<template>
  <div class="agent-markdown-answer markdown-preview-shell" data-math-style="classic">
    <span v-if="loading" class="answer-rendering">Rendering Markdown…</span>
    <article v-else class="markdown-body" v-html="html" />
  </div>
</template>
