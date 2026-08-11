<script setup lang="ts">
import { computed, defineAsyncComponent, onBeforeUnmount, ref, watch } from 'vue'
import { detectCapabilities } from '../math-visualizer/core/CapabilityDetector'
import { PerformanceManager } from '../math-visualizer/core/PerformanceManager'
import { resolveQuality } from '../math-visualizer/core/quality'
import PerformanceSelector from '../math-visualizer/components/PerformanceSelector.vue'
import RendererDebugPanel from '../math-visualizer/components/RendererDebugPanel.vue'
import type { MathModuleId, QualityMode, QualityProfile, RendererId, RendererTelemetry } from '../math-visualizer/types'
import type { FormulaLaunchRequest } from '../math-visualizer/core/formulaRouter'
import '../math-visualizer/styles/math-lab.css'

const props = defineProps<{ launchRequest?: FormulaLaunchRequest | null }>()
const emit = defineEmits<{ close: [] }>()

const LinearTransformModule = defineAsyncComponent(() => import('../math-visualizer/modules/linear-algebra/LinearTransformModule.vue'))
const ComplexMappingModule = defineAsyncComponent(() => import('../math-visualizer/modules/complex-analysis/ComplexMappingModule.vue'))
const FourierModule = defineAsyncComponent(() => import('../math-visualizer/modules/fourier/FourierModule.vue'))
const LaplaceModule = defineAsyncComponent(() => import('../math-visualizer/modules/laplace/LaplaceModule.vue'))
const SurfaceModule = defineAsyncComponent(() => import('../math-visualizer/modules/surfaces/SurfaceModule.vue'))

const modules = [
  { id: 'linear', label: 'Linear Transform', caption: 'Matrix state → grid, basis, area and eigendirections' },
  { id: 'complex', label: 'Complex Mapping', caption: 'Dual planes, draggable points and domain coloring' },
  { id: 'fourier', label: 'Fourier', caption: 'Signal, complex wrapping, integral and spectrum' },
  { id: 'laplace', label: 'Laplace', caption: 'Decay, rotation and transform value across the s-plane' },
  { id: 'surface', label: '3D Surface', caption: 'Precise surfaces with orbit, wireframe and fallback' },
] as const
const selected = ref<MathModuleId>('linear')
const mode = ref<QualityMode>('auto')
const capabilities = detectCapabilities()
const adaptiveProfile = ref<QualityProfile | null>(null)
const profile = computed(() => adaptiveProfile.value || resolveQuality(mode.value, capabilities))
const telemetry = ref<RendererTelemetry | null>(null)
const renderer = ref<RendererId | null>(null)
const activeLaunch = ref<FormulaLaunchRequest | null>(null)
let manager = new PerformanceManager(profile.value, true)

const selectedMeta = computed(() => modules.find((item) => item.id === selected.value)!)
const selectedComponent = computed(() => ({ linear: LinearTransformModule, complex: ComplexMappingModule, fourier: FourierModule, laplace: LaplaceModule, surface: SurfaceModule }[selected.value]))
const routedExpression = computed(() => activeLaunch.value?.module === selected.value ? activeLaunch.value.expression : '')

watch(mode, () => {
  adaptiveProfile.value = null
  manager = new PerformanceManager(resolveQuality(mode.value, capabilities), mode.value === 'auto')
})
watch(() => props.launchRequest, (request) => {
  if (!request) return
  activeLaunch.value = request
  selected.value = request.module
  telemetry.value = null
  renderer.value = null
}, { immediate: true })

function receiveTelemetry(value: RendererTelemetry) {
  telemetry.value = value
  const adjusted = manager.recordFrame(value.frameTime)
  if (adjusted && mode.value === 'auto') adaptiveProfile.value = adjusted
}

function switchModule(event: Event) {
  const module = (event.target as HTMLSelectElement).value as MathModuleId
  selected.value = module
  if (activeLaunch.value) activeLaunch.value = { ...activeLaunch.value, module, automatic: false }
  telemetry.value = null
  renderer.value = null
}
onBeforeUnmount(() => { activeLaunch.value = null })
</script>

<template>
  <div class="math-lab-shell">
    <header class="math-lab-header">
      <button type="button" class="math-document-return" @click="emit('close')">← RETURN TO DOCUMENT</button>
      <div class="math-lab-title"><span>FORMULA WINDOW / ISOLATED WORKSPACE</span><h1>{{ selectedMeta.label }}</h1><p>{{ selectedMeta.caption }}</p></div>
      <div class="math-lab-system"><label class="math-module-selector"><span>VISUALIZATION SYSTEM</span><select :value="selected" @change="switchModule"><option v-for="item in modules" :key="item.id" :value="item.id">{{ item.label }}</option></select></label><PerformanceSelector v-model="mode" :resolved-tier="profile.tier" /></div>
    </header>

    <template>
      <section class="math-workspace-status"><span><i />{{ renderer ? `${renderer.toUpperCase()} ACTIVE` : 'STARTING RENDERER' }}</span><span>{{ profile.surfaceResolution }}² SURFACE · {{ profile.complexResolution }} COMPLEX · DPR {{ profile.maxDpr }}</span></section>
      <section v-if="activeLaunch" class="math-import-banner"><div><span>MARKDOWN FORMULA / ROUTED TO {{ selectedMeta.label.toUpperCase() }}</span><code>{{ activeLaunch.expression }}</code></div><b>{{ activeLaunch.automatic ? `${activeLaunch.confidence.toUpperCase()} AUTO MATCH` : 'MANUAL ROUTE' }}</b></section>
      <Suspense><component :is="selectedComponent" :key="`${selected}-${activeLaunch?.id || 0}`" :profile="profile" :capabilities="capabilities" :initial-expression="routedExpression" @renderer="renderer = $event" @telemetry="receiveTelemetry" /><template #fallback><div class="math-module-loader panel"><i /><b>LOADING {{ selectedMeta.label.toUpperCase() }}</b><span>Heavy code is requested only now.</span></div></template></Suspense>
      <RendererDebugPanel :telemetry="telemetry" :profile="profile" :capabilities="capabilities" />
    </template>
  </div>
</template>
