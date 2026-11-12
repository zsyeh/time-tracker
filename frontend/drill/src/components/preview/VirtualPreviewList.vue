<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useVirtualizer } from '@tanstack/vue-virtual'
import PreviewQuestionRow from './PreviewQuestionRow.vue'
import type { PreviewAnchor, PreviewItem } from '../../lib/listContext'
import type { PreviewImagePipeline } from '../../lib/preview/imagePipeline'
import { estimatePreviewHeight, previewRange, rememberBounded } from '../../lib/preview/layout'
const props = defineProps<{ count: number; version: string; revision: number; getItem: (index: number) => PreviewItem | undefined; pipeline: PreviewImagePipeline; paperSnapshot?: boolean }>()
const emit = defineEmits<{ range: [first: number, last: number]; anchor: [anchor: PreviewAnchor]; open: [item: PreviewItem]; zoom: [item: PreviewItem] }>()
const scroller = ref<HTMLElement | null>(null), viewportHeight = ref(600), width = ref(600), backward = ref(false)
const identities = new Map<number,string>(), heights = new Map<string,number>()
// Numeric positioning only (4 bytes/index), not question metadata or identities.
// Keep prior estimates when a metadata page/key leaves the 500-item LRU;
// otherwise all later offsets jump when known scans become placeholders again.
let sizeLedger = new Float32Array(props.count)
let resizeObserver: ResizeObserver | undefined, styleObserver: MutationObserver | undefined, restoreSerial = 0, resizeFrame = 0
let lastAnchor: PreviewAnchor | null = null, previousWidth = 0
let fontSignature = ''
const currentFont = () => `${document.documentElement.style.getPropertyValue('--ui-font-scale')}:${document.documentElement.dataset.fontSize ?? ''}`
function keyFor(index: number) {
 const item = props.getItem(index)
 if (item) rememberBounded(identities, index, item.entry_id)
 return identities.get(index) ?? `${props.version}:${index}`
}
function estimate(index: number) {
 const recorded = sizeLedger[index]; if (recorded && recorded > 0) return recorded
 const item = props.getItem(index)
 const size = estimatePreviewHeight(item?.preview.assets, width.value, item?.preview.question_markdown)
 if(index >= 0 && index < sizeLedger.length) sizeLedger[index] = size
 return size
}
const virtualizer = useVirtualizer(computed(() => {
 // Session is deliberately non-reactive; revision is its bounded cache epoch.
 void props.revision
 return {
  count: props.count, getScrollElement: () => scroller.value, estimateSize: estimate,
  getItemKey: (index: number) => `${props.version}:${index}`, overscan: 0,
  rangeExtractor: (range: { startIndex: number; endIndex: number; count: number }) => previewRange(range.startIndex, range.endIndex, range.count, viewportHeight.value, estimate, backward.value),
  measureElement: (element: HTMLElement) => { const size = element.getBoundingClientRect().height; const index = Number(element.dataset.index); rememberBounded(heights, keyFor(index), size); if(index >= 0 && index < sizeLedger.length) sizeLedger[index] = size; return size },
 }
}))
const rows = computed(() => { void props.revision; return virtualizer.value.getVirtualItems() })
const totalSize = computed(() => virtualizer.value.getTotalSize())
const atEnd = computed(() => rows.value.at(-1)?.index === props.count - 1)
function measure(element: unknown) { virtualizer.value.measureElement(element instanceof HTMLElement ? element : null) }
function captureAnchor(): PreviewAnchor | null {
 const root = scroller.value; if (!root) return lastAnchor
 const offset = root.scrollTop
 const row = virtualizer.value.getVirtualItems().find(item => item.end > offset + 1)
 if (!row) return lastAnchor
 const item = props.getItem(row.index)
 if (!item) return lastAnchor
 return { entry_id:item.entry_id, question_uuid:item.question_uuid, index:item.index, offset:row.start - offset, collection_version:props.version, scrollTop:offset }
}
function rememberAnchor() { backward.value = virtualizer.value.scrollDirection === 'backward'; const anchor = captureAnchor(); if (anchor) { lastAnchor = anchor; emit('anchor', anchor) } }
function cancelRestore() { restoreSerial++ }
async function restoreAnchor(anchor: PreviewAnchor) {
 const serial = ++restoreSerial
 await nextTick(); if (serial !== restoreSerial || !props.count) return
 const index = Math.min(props.count - 1, Math.max(0, anchor.index))
 virtualizer.value.scrollToIndex(index, { align:'start', behavior:'auto' })
 // Two measured frames settle row refs/ResizeObserver without competing with touch momentum.
 for (let attempt = 0; attempt < 3; attempt++) {
  await new Promise<void>(resolve => requestAnimationFrame(() => resolve()))
  if (serial !== restoreSerial) return
  const row = virtualizer.value.getVirtualItems().find(row => row.index === index)
  if (row) virtualizer.value.scrollToOffset(Math.max(0, row.start - anchor.offset), { behavior:'auto' })
 }
 rememberAnchor()
}
function scrollToIndex(index: number) {
 cancelRestore()
 const item = props.getItem(index)
 if (item) void restoreAnchor({entry_id:item.entry_id,question_uuid:item.question_uuid,index,offset:0,collection_version:props.version})
 else virtualizer.value.scrollToIndex(index, { align:'start', behavior:'auto' })
}
function resize() {
 cancelAnimationFrame(resizeFrame)
 resizeFrame = requestAnimationFrame(() => {
  const root = scroller.value; if (!root) return
  const anchor = lastAnchor
  viewportHeight.value = Math.max(160, (window.visualViewport?.height ?? window.innerHeight) - root.getBoundingClientRect().top - 12)
  const nextWidth = root.clientWidth
  if (nextWidth !== previousWidth) {
   width.value = nextWidth; previousWidth = nextWidth; heights.clear(); sizeLedger.fill(0); virtualizer.value.measure()
   if (anchor) void restoreAnchor(anchor)
  }
 })
}
watch(() => [props.version, props.count], ([version], [oldVersion]) => {
 if (version !== oldVersion) { identities.clear(); heights.clear(); sizeLedger = new Float32Array(props.count); virtualizer.value.measure() }
 else if (sizeLedger.length !== props.count) { const next = new Float32Array(props.count); next.set(sizeLedger.subarray(0, Math.min(props.count,sizeLedger.length))); sizeLedger = next; virtualizer.value.measure() }
}, { flush:'post' })
watch(() => props.revision, rememberAnchor, { flush:'post' })
watch(() => rows.value.map(row => row.index).join(','), () => {
 const list = rows.value
 if (list.length) emit('range', list[0]!.index, list[list.length - 1]!.index)
 rememberAnchor()
}, { flush:'post' })
onMounted(() => {
 resize(); resizeObserver = new ResizeObserver(resize); if (scroller.value) resizeObserver.observe(scroller.value)
 fontSignature = currentFont()
 styleObserver = new MutationObserver(() => { const next = currentFont(); if(next === fontSignature) return; fontSignature = next; heights.clear(); sizeLedger.fill(0); virtualizer.value.measure(); resize(); if(lastAnchor) void restoreAnchor(lastAnchor) })
 styleObserver.observe(document.documentElement, { attributes:true, attributeFilter:['style','data-font-size'] })
 window.addEventListener('resize', resize); window.visualViewport?.addEventListener('resize', resize)
})
onBeforeUnmount(() => { rememberAnchor(); cancelRestore(); cancelAnimationFrame(resizeFrame); resizeObserver?.disconnect(); styleObserver?.disconnect(); window.removeEventListener('resize', resize); window.visualViewport?.removeEventListener('resize', resize) })
defineExpose({ captureAnchor, restoreAnchor, scrollToIndex, scroller, getMountedCount: () => rows.value.length })
</script>
<template>
 <div ref="scroller" class="preview-scroller" tabindex="0" role="region" aria-label="题单预览，向上或向下滚动浏览" :style="{ height: `${viewportHeight}px` }" :data-mounted-rows="rows.length" :data-visible-budget-exception="rows.length > 20" @scroll.passive="rememberAnchor" @wheel.passive="cancelRestore" @touchstart.passive="cancelRestore" @keydown="cancelRestore">
  <div class="preview-spacer" :style="{ height: `${totalSize + 44}px` }">
   <div class="preview-window" :style="{ transform: `translateY(${rows[0]?.start ?? 0}px)` }">
    <div v-for="row in rows" :key="String(row.key)" :ref="measure" :data-index="row.index" class="preview-row">
     <PreviewQuestionRow v-if="getItem(row.index)" :key="getItem(row.index)!.entry_id" :item="getItem(row.index)!" :pipeline="pipeline" :scroller="scroller" :paper-snapshot="paperSnapshot" @open="emit('open', $event)" @zoom="emit('zoom', $event)" />
     <div v-else class="preview-row-loading" :style="{ minHeight: `${estimate(row.index)}px` }" aria-busy="true">第 {{ row.index + 1 }} 题 · 正在加载…</div>
    </div>
   </div>
   <p v-if="atEnd && count" class="preview-end" :style="{ top: `${totalSize}px` }" role="status">已到题单末尾 · 共 {{ count }} 题</p>
  </div>
 </div>
</template>
<style scoped>
.preview-scroller{position:relative;overflow:auto;overscroll-behavior-y:contain;overflow-anchor:none;scroll-behavior:auto;min-width:0;touch-action:pan-y pinch-zoom;scrollbar-gutter:stable;padding-bottom:env(safe-area-inset-bottom,0px);box-sizing:border-box}
.preview-spacer{width:100%;position:relative}
.preview-window{position:absolute;top:0;left:0;width:100%}
.preview-end{position:absolute;left:0;width:100%;margin:0;min-height:44px;display:grid;place-items:center;font-size:13px;color:var(--text-secondary,#999)}
.preview-row{width:100%;min-width:0;box-sizing:border-box}
.preview-row-loading{padding:16px;color:var(--text-secondary,#999);font-size:14px;box-sizing:border-box}
.preview-scroller:focus-visible{outline:2px solid var(--accent,#6ba6ff);outline-offset:2px}
</style>
