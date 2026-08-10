<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Close, FullScreen } from '@element-plus/icons-vue'

const props = withDefaults(defineProps<{
  source: string
  showSource?: boolean
  defaultOpen?: boolean
  emptyText?: string
  allowFullscreen?: boolean
}>(), {
  showSource: false,
  defaultOpen: false,
  emptyText: 'No Markdown content.',
  allowFullscreen: false,
})

const previewOpen = ref(props.defaultOpen)
const loading = ref(false)
const rendered = ref('')
const fullscreen = ref(false)
let previousOverflow = ''
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
  if (fullscreen.value) return
  previewOpen.value = !previewOpen.value
  if (previewOpen.value) scheduleRender()
}

function toggleFullscreen() {
  fullscreen.value = !fullscreen.value
  if (fullscreen.value) {
    previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    if (!previewOpen.value) { previewOpen.value = true; scheduleRender() }
  } else {
    document.body.style.overflow = previousOverflow
  }
}

function closeFullscreenWithEscape(event: KeyboardEvent) {
  if (fullscreen.value && event.key === 'Escape') {
    event.preventDefault()
    event.stopPropagation()
    toggleFullscreen()
  }
}

watch(() => props.source, () => {
  rendered.value = ''
  if (previewOpen.value) scheduleRender(220)
})
onMounted(() => {
  window.addEventListener('keydown', closeFullscreenWithEscape, true)
  if (previewOpen.value) scheduleRender()
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', closeFullscreenWithEscape, true)
  if (timer) clearTimeout(timer)
  if (fullscreen.value) document.body.style.overflow = previousOverflow
})
</script>

<template>
  <div class="markdown-preview-shell" :class="{ 'source-enabled': showSource, 'is-fullscreen': fullscreen }">
    <div class="markdown-preview-toolbar">
      <button v-if="!fullscreen" type="button" class="markdown-preview-toggle" :aria-expanded="previewOpen" @click="togglePreview">
        {{ previewOpen ? (showSource ? 'Show source' : 'Hide preview') : 'Preview Markdown' }}
      </button>
      <span>KaTeX · GFM · code · footnotes · callouts</span>
      <button v-if="allowFullscreen && (previewOpen || fullscreen)" type="button" class="markdown-fullscreen-toggle" :aria-label="fullscreen ? 'Exit full screen' : 'Open full screen'" @click="toggleFullscreen">
        <el-icon><Close v-if="fullscreen" /><FullScreen v-else /></el-icon><span>{{ fullscreen ? 'EXIT' : 'FULL SCREEN' }}</span>
      </button>
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
