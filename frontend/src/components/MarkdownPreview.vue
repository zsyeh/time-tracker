<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Close, FullScreen } from '@element-plus/icons-vue'
import { mathVisualizationEnabled } from '../lib/featureFlags'
import type { FormulaLaunchRequest } from '../math-visualizer/core/formulaRouter'

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
const fullscreenDialog = ref<HTMLDialogElement | null>(null)
const fullscreenScroll = ref<HTMLElement | null>(null)
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
    const html = renderMarkdown(source, { mathVisualization: mathVisualizationEnabled.value })
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

function restorePageScroll() {
  document.body.style.overflow = previousOverflow
  document.documentElement.classList.remove('markdown-reading-open')
}

async function enterFullscreen() {
  if (fullscreen.value) return
  previousOverflow = document.body.style.overflow
  document.body.style.overflow = 'hidden'
  document.documentElement.classList.add('markdown-reading-open')
  fullscreen.value = true
  if (!previewOpen.value) { previewOpen.value = true; scheduleRender() }
  await nextTick()
  const dialog = fullscreenDialog.value
  if (dialog && !dialog.open) {
    try { dialog.showModal() } catch { dialog.setAttribute('open', '') }
  }
  await nextTick()
  fullscreenScroll.value?.focus({ preventScroll: true })
}

function exitFullscreen() {
  if (!fullscreen.value) return
  const dialog = fullscreenDialog.value
  if (dialog?.open) dialog.close()
  fullscreen.value = false
  restorePageScroll()
}

function toggleFullscreen() {
  if (fullscreen.value) exitFullscreen()
  else void enterFullscreen()
}

function onNativeDialogClose() {
  if (!fullscreen.value) return
  fullscreen.value = false
  restorePageScroll()
}

function onFullscreenCancel() {
  exitFullscreen()
}

async function handleRenderedClick(event: MouseEvent) {
  if (!mathVisualizationEnabled.value) return
  const button = (event.target as Element | null)?.closest<HTMLElement>('[data-math-launch]')
  if (!button) return
  event.preventDefault()
  event.stopPropagation()
  try {
    const expression = decodeURIComponent(button.dataset.mathLaunch || '')
    if (!expression.trim()) return
    const { routeFormula } = await import('../math-visualizer/core/formulaRouter')
    const route = routeFormula(expression)
    const request: FormulaLaunchRequest = { ...route, expression, id: Date.now(), automatic: true }
    requestAnimationFrame(() => window.dispatchEvent(new CustomEvent('learning-os-open-math-lab', { detail: request })))
  } catch {
    ElMessage.error('Unable to read this formula.')
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
watch(mathVisualizationEnabled, () => {
  rendered.value = ''
  if (previewOpen.value) scheduleRender()
})
onMounted(() => {
  window.addEventListener('learning-os-math-style', syncMathStyle)
  if (previewOpen.value) scheduleRender()
})
onBeforeUnmount(() => {
  window.removeEventListener('learning-os-math-style', syncMathStyle)
  if (timer) clearTimeout(timer)
  if (fullscreen.value) restorePageScroll()
})
</script>

<template>
  <div class="markdown-preview-shell" :class="{ 'source-enabled': showSource }" :data-math-style="mathStyle">
    <div class="markdown-preview-toolbar">
      <button type="button" class="markdown-preview-toggle" :aria-expanded="previewOpen" @click="togglePreview">
        {{ previewOpen ? (showSource ? 'Show source' : 'Hide preview') : 'Preview Markdown' }}
      </button>
      <span>KaTeX · GFM · code · footnotes · callouts</span>
      <label v-if="previewOpen" class="markdown-math-style">
        <span>MATH STYLE</span>
        <select :value="mathStyle" aria-label="Formula rendering style" @change="setMathStyle">
          <option v-for="style in mathStyles" :key="style.id" :value="style.id">{{ style.label }}</option>
        </select>
      </label>
      <button v-if="allowFullscreen && previewOpen" type="button" class="markdown-fullscreen-toggle" aria-label="Open immersive reader" @click="toggleFullscreen">
        <el-icon><FullScreen /></el-icon><span>IMMERSIVE</span>
      </button>
    </div>
    <el-collapse-transition>
      <section v-if="previewOpen" v-loading="loading" class="markdown-preview-panel">
        <div v-if="source.trim()" class="markdown-body" v-html="rendered" @click="handleRenderedClick" />
        <p v-else class="markdown-empty">{{ emptyText }}</p>
      </section>
      <pre v-else-if="showSource" class="markdown-source">{{ source || emptyText }}</pre>
    </el-collapse-transition>
  </div>

  <Teleport to="body">
    <dialog
      v-if="fullscreen"
      ref="fullscreenDialog"
      class="markdown-reading-portal"
      :data-math-style="mathStyle"
      aria-label="Immersive Markdown reader"
      @cancel.prevent="onFullscreenCancel"
      @close="onNativeDialogClose"
      @pointerdown.stop
      @wheel.stop
      @touchstart.stop
    >
      <div class="reading-portal-frame">
        <header class="reading-portal-header">
          <div class="reading-portal-identity"><i /><div><span>LEARNING OS / READER</span><strong>Immersive document environment</strong></div></div>
          <div class="reading-portal-actions">
            <label class="markdown-math-style"><span>FORMULA</span><select :value="mathStyle" aria-label="Formula rendering style" @change="setMathStyle"><option v-for="style in mathStyles" :key="style.id" :value="style.id">{{ style.label }}</option></select></label>
            <button type="button" class="reading-exit-button" aria-label="Exit immersive reader" @click="exitFullscreen"><el-icon><Close /></el-icon><span>EXIT</span></button>
          </div>
        </header>
        <aside class="reading-portal-rail" aria-hidden="true"><b>REVIEW</b><i /><span>DOCUMENT</span><span>FORMULA</span><small>ESC TO EXIT</small></aside>
        <main ref="fullscreenScroll" v-loading="loading" class="reading-portal-scroll" tabindex="-1" @touchmove.stop>
          <article class="reading-portal-document">
            <div class="reading-document-meta"><span>MARKDOWN DOCUMENT</span><b>READING MODE</b></div>
            <div v-if="source.trim()" class="markdown-body" v-html="rendered" @click="handleRenderedClick" />
            <p v-else class="markdown-empty">{{ emptyText }}</p>
          </article>
        </main>
        <footer class="reading-portal-footer"><span>LOCAL RENDER · SANITIZED HTML · KATEX</span><b>SCROLL DOCUMENT</b></footer>
      </div>
    </dialog>
  </Teleport>
</template>
