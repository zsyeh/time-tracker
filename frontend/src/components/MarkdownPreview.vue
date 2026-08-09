<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

const props = withDefaults(defineProps<{
  source: string
  showSource?: boolean
  defaultOpen?: boolean
  emptyText?: string
}>(), {
  showSource: false,
  defaultOpen: false,
  emptyText: 'No Markdown content.',
})

const previewOpen = ref(props.defaultOpen)
const loading = ref(false)
const rendered = ref('')
let timer: ReturnType<typeof setTimeout> | undefined
let version = 0

async function renderNow() {
  if (!previewOpen.value) return
  const source = props.source || ''
  if (!source.trim()) { rendered.value = ''; return }
  const requestVersion = ++version
  loading.value = true
  try {
    await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()))
    const { renderMarkdown } = await import('../lib/markdown')
    const html = renderMarkdown(source)
    if (requestVersion === version) rendered.value = html
  } catch (error) {
    ElMessage.error(`Markdown preview failed: ${(error as Error).message}`)
  } finally {
    if (requestVersion === version) loading.value = false
  }
}

function scheduleRender(delay = 0) {
  if (timer) clearTimeout(timer)
  timer = setTimeout(renderNow, delay)
}

function togglePreview() {
  previewOpen.value = !previewOpen.value
  if (previewOpen.value) scheduleRender()
}

watch(() => props.source, () => {
  rendered.value = ''
  if (previewOpen.value) scheduleRender(220)
})
onBeforeUnmount(() => { if (timer) clearTimeout(timer) })
</script>

<template>
  <div class="markdown-preview-shell" :class="{ 'source-enabled': showSource }">
    <div class="markdown-preview-toolbar">
      <button type="button" class="markdown-preview-toggle" :aria-expanded="previewOpen" @click="togglePreview">
        {{ previewOpen ? (showSource ? 'Show source' : 'Hide preview') : 'Preview Markdown' }}
      </button>
      <span>KaTeX · GFM · code · footnotes · callouts</span>
    </div>
    <el-collapse-transition>
      <section v-if="previewOpen" v-loading="loading" class="markdown-preview-panel">
        <div v-if="source.trim()" class="markdown-body" v-html="rendered" />
        <p v-else class="markdown-empty">{{ emptyText }}</p>
      </section>
      <pre v-else-if="showSource" class="markdown-source">{{ source || emptyText }}</pre>
    </el-collapse-transition>
  </div>
</template>
