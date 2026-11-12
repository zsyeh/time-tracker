<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import type { PreviewAsset } from '../../lib/listContext'
import type { PreviewImageHandle, PreviewImagePipeline, PreviewImageState } from '../../lib/preview/imagePipeline'
import { withWorkspacePrefix } from '../../lib/runtimePath'
const props = defineProps<{ asset: PreviewAsset; pipeline: PreviewImagePipeline; scroller: HTMLElement | null; label: string; openLabel?: string }>()
const emit = defineEmits<{ open: [] }>()
const root = ref<HTMLElement | null>(null)
const state = shallowRef<PreviewImageState>({ status: 'waiting' })
let nearObserver: IntersectionObserver | undefined, visibleObserver: IntersectionObserver | undefined, handle: PreviewImageHandle | undefined
let near = false, visible = false
const pointers = new Map<number, { x:number; y:number }>()
let gestureBlocked = false
function pointerDown(event: PointerEvent) {
 // Receive the matching pointerup even if a mouse drag leaves the image.
 try { (event.currentTarget as HTMLElement).setPointerCapture?.(event.pointerId) } catch { /* Pointer may already have been cancelled by native scrolling. */ }
 if (!pointers.size) gestureBlocked = false
 pointers.set(event.pointerId,{x:event.clientX,y:event.clientY})
 if (pointers.size > 1 || !event.isPrimary) gestureBlocked = true
}
function pointerMove(event: PointerEvent) { const start=pointers.get(event.pointerId); if(start && Math.hypot(event.clientX-start.x,event.clientY-start.y)>8) gestureBlocked=true }
function pointerEnd(event: PointerEvent) { pointers.delete(event.pointerId); if(event.type==='pointercancel') gestureBlocked=true }
function openImage() { if(!gestureBlocked && state.value.status==='ready') emit('open') }
function sync() {
 if (near && !handle) handle = props.pipeline.request({ ...props.asset, url: withWorkspacePrefix(props.asset.url) }, value => { state.value = value }, visible ? 0 : 2)
 if (!near && handle) { handle.release(); handle = undefined; state.value = { status: 'waiting' } }
 handle?.priority(visible ? 0 : 2)
}
function observe() {
 nearObserver?.disconnect(); visibleObserver?.disconnect(); handle?.release(); handle = undefined; near = false; visible = false
 if (!root.value || !props.scroller) return
 nearObserver = new IntersectionObserver(entries => { near = entries[0]?.isIntersecting ?? false; sync() }, { root: props.scroller, rootMargin: '200% 0px' })
 visibleObserver = new IntersectionObserver(entries => { visible = entries[0]?.isIntersecting ?? false; if (visible) near = true; sync() }, { root: props.scroller })
 nearObserver.observe(root.value); visibleObserver.observe(root.value)
}
onMounted(observe)
watch(() => [props.asset.url, props.scroller], observe, { flush: 'post' })
onBeforeUnmount(() => { nearObserver?.disconnect(); visibleObserver?.disconnect(); handle?.release() })
</script>
<template>
 <figure ref="root" class="preview-asset" :style="{ aspectRatio: asset.width > 0 && asset.height > 0 ? `${asset.width}/${asset.height}` : 'auto', minHeight: asset.width > 0 && asset.height > 0 ? '44px' : '160px' }">
  <button v-if="state.status === 'ready'" type="button" class="preview-image-open" :aria-label="`${label}，${openLabel || '进入做题'}`" @click.stop="openImage" @pointerdown.passive="pointerDown" @pointermove.passive="pointerMove" @pointerup.passive="pointerEnd" @pointercancel.passive="pointerEnd" @keydown="gestureBlocked = false"><img :src="state.url" :width="asset.width || undefined" :height="asset.height || undefined" :alt="label" decoding="async" draggable="false" /></button>
  <div v-else class="preview-asset-placeholder" :role="state.status === 'error' ? 'alert' : undefined">
   <template v-if="state.status === 'error'">题图加载失败 <button type="button" @click="handle?.retry()">重试</button></template>
   <span v-else>{{ state.status === 'loading' ? '正在加载题图…' : '题图预览' }}</span>
  </div>
 </figure>
</template>
<style scoped>
.preview-asset{position:relative;margin:8px 0 0;width:100%;overflow:hidden;background:#fff;color:#333;border-radius:4px}
.preview-asset img{display:block;width:100%;height:auto;touch-action:pan-y pinch-zoom}
.preview-asset-placeholder{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;gap:8px;font-size:13px;color:#626262;background:#f4f4f4}
.preview-asset button{min-width:44px;min-height:44px;border:0;border-radius:6px;padding:8px;background:#eee;color:#222;font:inherit;cursor:pointer}
.preview-asset .preview-image-open{display:block;width:100%;padding:0;border:0;border-radius:0;background:transparent;touch-action:pan-y pinch-zoom}
.preview-asset button:focus-visible{outline:2px solid var(--accent,#6ba6ff);outline-offset:2px}
</style>
