<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Close, FullScreen } from '@element-plus/icons-vue'

type MathStyle = 'classic' | 'minimal' | 'paper' | 'blueprint'

const mathStyles: Array<{ id: MathStyle; label: string }> = [
  { id: 'classic', label: 'Classic' },
  { id: 'minimal', label: 'Minimal' },
  { id: 'paper', label: 'Paper' },
  { id: 'blueprint', label: 'Blueprint' },
]
const mathStyleKey = 'learning-os-math-style'

function savedMathStyle(): MathStyle {
  try {
    const saved = localStorage.getItem(mathStyleKey)
    return mathStyles.some((style) => style.id === saved) ? saved as MathStyle : 'classic'
  } catch {
    return 'classic'
  }
}

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
const mathStyle = ref<MathStyle>(savedMathStyle())
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

function setMathStyle(event: Event) {
  const value = (event.target as HTMLSelectElement).value as MathStyle
  mathStyle.value = value
  try { localStorage.setItem(mathStyleKey, value) } catch { /* Storage may be disabled. */ }
  window.dispatchEvent(new CustomEvent('learning-os-math-style', { detail: value }))
}

function syncMathStyle(event: Event) {
  const value = (event as CustomEvent<MathStyle>).detail
  if (mathStyles.some((style) => style.id === value)) mathStyle.value = value
}

watch(() => props.source, () => {
  rendered.value = ''
  if (previewOpen.value) scheduleRender(220)
})
onMounted(() => {
  window.addEventListener('keydown', closeFullscreenWithEscape, true)
  window.addEventListener('learning-os-math-style', syncMathStyle)
  if (previewOpen.value) scheduleRender()
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', closeFullscreenWithEscape, true)
  window.removeEventListener('learning-os-math-style', syncMathStyle)
  if (timer) clearTimeout(timer)
  if (fullscreen.value) document.body.style.overflow = previousOverflow
})
</script>

<template>
  <Teleport to="body" :disabled="!fullscreen">
    <div class="markdown-preview-shell" :class="{ 'source-enabled': showSource, 'is-fullscreen': fullscreen }" :data-math-style="mathStyle">
      <div class="markdown-preview-toolbar">
        <button v-if="!fullscreen" type="button" class="markdown-preview-toggle" :aria-expanded="previewOpen" @click="togglePreview">
          {{ previewOpen ? (showSource ? 'Show source' : 'Hide preview') : 'Preview Markdown' }}
        </button>
        <span>KaTeX · GFM · code · footnotes · callouts</span>
        <label v-if="previewOpen" class="markdown-math-style">
          <span>MATH STYLE</span>
          <select :value="mathStyle" aria-label="Formula rendering style" @change="setMathStyle">
            <option v-for="style in mathStyles" :key="style.id" :value="style.id">{{ style.label }}</option>
          </select>
        </label>
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
  </Teleport>
</template>
