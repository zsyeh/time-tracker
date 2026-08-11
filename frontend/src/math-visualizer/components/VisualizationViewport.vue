<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { createRenderer, selectRenderer } from '../renderers/rendererFactory'
import type { MathRenderer, MathScene, QualityProfile, RendererId, RendererTelemetry, RuntimeCapabilities, Vec2 } from '../types'

const props = defineProps<{ scene: MathScene; profile: QualityProfile; capabilities: RuntimeCapabilities }>()
const emit = defineEmits<{ renderer: [id: RendererId]; error: [message: string]; telemetry: [value: RendererTelemetry]; pointChange: [value: Vec2] }>()
const container = ref<HTMLElement | null>(null)
const renderer = shallowRef<MathRenderer | null>(null)
const loading = ref(true)
const fallback = ref('')
const desiredRenderer = computed(() => selectRenderer(props.scene, props.profile, props.capabilities))
let resizeObserver: ResizeObserver | null = null
let generation = 0
let time = 1
let frameCount = 0
let frameTotal = 0
let lastTelemetry = performance.now()

async function initialize() {
  const host = container.value
  if (!host) return
  const version = ++generation
  loading.value = true
  fallback.value = ''
  renderer.value?.dispose()
  renderer.value = null
  try {
    const next = await createRenderer(desiredRenderer.value)
    next.setQuality(props.profile)
    await next.init(host)
    if (version !== generation) { next.dispose(); return }
    renderer.value = next
    resize()
    next.render(props.scene, time)
    emit('renderer', next.id)
  } catch (error) {
    if (version !== generation) return
    const message = `${desiredRenderer.value} initialization failed: ${(error as Error).message}`
    emit('error', message)
    fallback.value = 'Compatibility renderer active'
    try {
      const next = await createRenderer('canvas')
      next.setQuality(props.profile)
      await next.init(host)
      if (version !== generation) { next.dispose(); return }
      renderer.value = next
      resize()
      next.render(props.scene, time)
      emit('renderer', next.id)
    } catch (fallbackError) {
      emit('error', `Canvas fallback failed: ${(fallbackError as Error).message}`)
    }
  } finally {
    if (version === generation) loading.value = false
  }
}

function resize() {
  const host = container.value
  if (!host || !renderer.value) return
  const bounds = host.getBoundingClientRect()
  renderer.value.resize(bounds.width, bounds.height, Math.min(props.capabilities.devicePixelRatio, props.profile.maxDpr))
  renderer.value.render(props.scene, time)
}

function setTime(progress: number) {
  const started = performance.now()
  time = progress
  renderer.value?.render(props.scene, progress)
  const finished = performance.now()
  frameCount += 1
  frameTotal += finished - started
  if (finished - lastTelemetry >= 500 && container.value && renderer.value) {
    const bounds = container.value.getBoundingClientRect()
    const elapsed = finished - lastTelemetry
    emit('telemetry', { renderer: renderer.value.id, fps: frameCount / elapsed * 1000, frameTime: frameCount ? frameTotal / frameCount : 0, width: Math.round(bounds.width), height: Math.round(bounds.height), dpr: Math.min(props.capabilities.devicePixelRatio, props.profile.maxDpr) })
    frameCount = 0; frameTotal = 0; lastTelemetry = finished
  }
}

function visibility() { if (document.hidden) renderer.value?.pause(); else { renderer.value?.resume(); renderer.value?.render(props.scene, time) } }
function rendererError(event: Event) { const message = (event as CustomEvent<string>).detail; emit('error', message); fallback.value = message }
function pointChange(event: Event) { emit('pointChange', (event as CustomEvent<Vec2>).detail) }

watch(desiredRenderer, initialize)
watch(() => props.profile, (value) => { renderer.value?.setQuality(value); resize() }, { deep: true })
watch(() => props.scene, (value) => renderer.value?.render(value, time), { deep: true })
onMounted(async () => {
  await nextTick()
  resizeObserver = new ResizeObserver(resize)
  if (container.value) {
    resizeObserver.observe(container.value)
    container.value.addEventListener('math-renderer-error', rendererError)
    container.value.addEventListener('math-point-change', pointChange)
  }
  document.addEventListener('visibilitychange', visibility)
  await initialize()
})
onBeforeUnmount(() => {
  generation += 1
  resizeObserver?.disconnect()
  document.removeEventListener('visibilitychange', visibility)
  container.value?.removeEventListener('math-renderer-error', rendererError)
  container.value?.removeEventListener('math-point-change', pointChange)
  renderer.value?.dispose()
})
defineExpose({ setTime, retry: initialize })
</script>

<template>
  <div class="math-viewport-frame">
    <div ref="container" class="math-viewport-host" :aria-busy="loading" />
    <div v-if="loading" class="math-viewport-loading"><i /><span>INITIALIZING RENDERER</span></div>
    <span v-if="fallback" class="math-fallback-badge">{{ fallback }}</span>
  </div>
</template>
