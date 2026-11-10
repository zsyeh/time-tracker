<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref } from 'vue'
import MarkdownAnswer from './MarkdownAnswer.vue'
import { typeText } from '../lib/examTypes'

type Page = { src: string; width?: number; height?: number }
const props = defineProps<{ title: string; images: Page[]; markdown?: string; prepare?: () => Promise<void> }>()
const emit = defineEmits<{ opened: [] }>()
const dialog = ref<HTMLDialogElement | null>(null)
const scroller = ref<HTMLElement | null>(null)
const opened = ref(false)
const loading = ref(false)
const loadError = ref('')
const zoom = ref(100)
const page = ref(1)
const failed = ref<Record<number, boolean>>({})
const retries = ref<Record<number, number>>({})
const label = computed(() => `${typeText('全屏阅读', 'Read full screen')} · ${props.title}`)
let previousOverflow: string | null = null
let opener: HTMLElement | null = null
function restore() {
  opened.value = false
  if (previousOverflow !== null) document.body.style.overflow = previousOverflow
  previousOverflow = null
  if (opener?.isConnected) opener.focus({ preventScroll: true })
}
async function open() {
  if (opened.value) return
  opener = document.activeElement as HTMLElement | null
  zoom.value = 100; page.value = 1; failed.value = {}; retries.value = {}
  opened.value = true
  await nextTick()
  if (!dialog.value?.isConnected) return
  previousOverflow = document.body.style.overflow
  document.body.style.overflow = 'hidden'
  dialog.value.showModal()
  emit('opened')
  await loadContent()
}
async function loadContent() {
  if (!props.prepare) return
  loading.value = true; loadError.value = ''
  try { await props.prepare() } catch (reason) { loadError.value = reason instanceof Error ? reason.message : typeText('加载失败', 'Failed to load') } finally { loading.value = false }
}
function close() { dialog.value?.close(); restore() }
async function setZoom(value: number) {
  const root = scroller.value
  const document = root?.querySelector<HTMLElement>('.reader-document')
  const previousWidth = document?.getBoundingClientRect().width || 1
  const centerY = root ? root.scrollTop + root.clientHeight / 2 : 0
  const centerX = root ? root.scrollLeft + root.clientWidth / 2 : 0
  zoom.value = Math.min(250, Math.max(50, value))
  await nextTick()
  if (root && document) {
    const ratio = document.getBoundingClientRect().width / previousWidth
    root.scrollTop = centerY * ratio - root.clientHeight / 2
    root.scrollLeft = centerX * ratio - root.clientWidth / 2
  }
}
function keyboard(event: KeyboardEvent) {
  if (['+', '=', '-', '0'].includes(event.key)) {
    event.preventDefault()
    setZoom(event.key === '0' ? 100 : zoom.value + (event.key === '-' ? -25 : 25))
  }
}
function trackPage() {
  const root = scroller.value
  if (!root) return
  const top = root.getBoundingClientRect().top + root.clientHeight / 2
  const pages = [...root.querySelectorAll<HTMLElement>('[data-reader-page]')]
  const current = pages.findIndex((item) => item.getBoundingClientRect().bottom > top)
  if (current >= 0) page.value = current + 1
}
function src(item: Page, index: number) {
  const retry = retries.value[index]
  return item.src + (retry ? `${item.src.includes('?') ? '&' : '?'}reader_retry=${retry}` : '')
}
function retry(index: number) { retries.value[index] = (retries.value[index] || 0) + 1; failed.value[index] = false }
onBeforeUnmount(() => { if (dialog.value?.open) dialog.value.close(); if (previousOverflow !== null) restore() })
</script>

<template>
  <button type="button" class="fullscreen-trigger" :title="label" :aria-label="label" @click.stop="open">
    <svg width="15" height="15" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M7 3H3v4m10-4h4v4M3 13v4h4m10-4v4h-4" /></svg>
  </button>
  <Teleport to="body">
    <dialog ref="dialog" class="fullscreen-reader" :aria-label="title" @close="restore" @keydown="keyboard">
      <template v-if="opened">
        <header class="reader-toolbar">
          <strong>{{ title }}</strong>
          <span v-if="images.length > 1" class="reader-count">{{ page }} / {{ images.length }}</span>
          <div class="reader-zoom">
            <button type="button" :aria-label="typeText('缩小', 'Zoom out')" :disabled="zoom <= 50" @click="setZoom(zoom - 25)">−</button>
            <button type="button" :title="typeText('恢复适合宽度', 'Fit to width')" @click="setZoom(100)">{{ zoom }}%</button>
            <button type="button" :aria-label="typeText('放大', 'Zoom in')" :disabled="zoom >= 250" @click="setZoom(zoom + 25)">+</button>
          </div>
          <button type="button" class="reader-close" autofocus :aria-label="typeText('关闭全屏', 'Close full screen')" @click="close">✕</button>
        </header>
        <div ref="scroller" class="reader-scroll" tabindex="0" @scroll.passive="trackPage">
          <p v-if="loading" class="reader-hint" role="status">{{ typeText('正在加载…', 'Loading…') }}</p>
          <p v-if="loadError" class="reader-hint" role="alert">{{ loadError }} <button type="button" class="reader-load-retry" @click="loadContent">{{ typeText('重试', 'Retry') }}</button></p>
          <p v-if="images.length > 1" class="reader-hint">{{ typeText('多页内容，向下滑动继续查看', 'Multiple pages · scroll down to continue') }}</p>
          <p v-if="!loading && !loadError && !images.length && !markdown" class="reader-hint">{{ typeText('暂无可显示内容', 'No content available') }}</p>
          <div class="reader-document" :style="{ width: `${zoom}%`, maxWidth: `${12 * zoom}px` }">
            <figure v-for="(item, index) in images" :key="index" :data-reader-page="index + 1">
              <img v-if="!failed[index]" :src="src(item, index)" :width="item.width" :height="item.height" :alt="`${title} · ${index + 1}`" :loading="index === 0 ? 'eager' : 'lazy'" decoding="async" @error="failed[index] = true" @dblclick="setZoom(zoom === 100 ? 175 : 100)" />
              <button v-else type="button" class="reader-retry" @click="retry(index)">{{ typeText('图片加载失败，点击重试', 'Image failed to load · retry') }}</button>
              <figcaption v-if="images.length > 1">{{ index + 1 }} / {{ images.length }}</figcaption>
            </figure>
            <MarkdownAnswer v-if="markdown" class="reader-markdown" :source="markdown" />
          </div>
        </div>
      </template>
    </dialog>
  </Teleport>
</template>

<style scoped>
.fullscreen-trigger { flex: none; display: inline-grid; place-items: center; width: 28px; min-height: 28px; padding: 4px; border: 1px solid var(--border-default); border-radius: 5px; color: var(--text-secondary); background: var(--bg-sidebar); cursor: pointer; }
.fullscreen-trigger:hover { color: var(--accent); border-color: var(--accent); }
.fullscreen-reader { position: fixed; inset: 0; width: 100%; max-width: none; height: 100vh; height: 100dvh; max-height: none; margin: 0; padding: 0; border: 0; color: var(--text-primary); background: var(--bg-main); overflow: hidden; }
.fullscreen-reader[open] { display: flex; flex-direction: column; }
.fullscreen-reader::backdrop { background: #000b; }
.reader-toolbar { flex: none; display: flex; align-items: center; gap: 10px; min-height: 48px; padding: max(6px, env(safe-area-inset-top)) max(10px, env(safe-area-inset-right)) 6px max(10px, env(safe-area-inset-left)); border-bottom: 1px solid var(--border-default); background: var(--bg-surface); }
.reader-toolbar strong { min-width: 0; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; }
.reader-count { flex: none; color: var(--text-secondary); font-size: 11px; font-variant-numeric: tabular-nums; }
.reader-zoom { display: flex; gap: 3px; }
.reader-toolbar button { min-width: 34px; min-height: 34px; padding: 4px 7px; border: 1px solid var(--border-default); border-radius: 6px; color: var(--text-primary); background: var(--bg-sidebar); font-size: 12px; cursor: pointer; }
.reader-toolbar button:disabled { opacity: .4; }
.reader-toolbar .reader-close { min-width: 40px; }
.reader-scroll { flex: 1 1 0; min-height: 0; overflow: auto; overscroll-behavior: contain; -webkit-overflow-scrolling: touch; padding: 12px max(10px, env(safe-area-inset-right)) max(16px, env(safe-area-inset-bottom)) max(10px, env(safe-area-inset-left)); touch-action: pan-x pan-y pinch-zoom; }
.reader-document { min-width: 0; margin-inline: auto; }
.reader-document figure { max-width: none; margin: 0 auto 16px; }
.reader-document img { display: block; width: 100%; height: auto; background: white; border-radius: 3px; }
.reader-document figcaption, .reader-hint { color: var(--text-secondary); text-align: center; font-size: 11px; }
.reader-hint { margin: 0 0 10px; }
.reader-document figcaption { margin-top: 5px; }
.reader-markdown { max-width: none; margin: 0 auto; padding: 14px; }
.reader-retry { width: 100%; min-height: 100px; border: 1px dashed var(--border-default); border-radius: 5px; color: var(--text-primary); background: var(--bg-surface); cursor: pointer; }
@media (max-width: 500px) { .reader-toolbar { gap: 5px; } .reader-toolbar strong { font-size: 11px; } .reader-toolbar button { padding: 4px; } }
</style>
