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

const LinearTransformModule = defineAsyncComponent(() => import('../math-visualizer/modules/linear-algebra/LinearTransformModule.vue'))
const ComplexMappingModule = defineAsyncComponent(() => import('../math-visualizer/modules/complex-analysis/ComplexMappingModule.vue'))
const FourierModule = defineAsyncComponent(() => import('../math-visualizer/modules/fourier/FourierModule.vue'))
const LaplaceModule = defineAsyncComponent(() => import('../math-visualizer/modules/laplace/LaplaceModule.vue'))
const SurfaceModule = defineAsyncComponent(() => import('../math-visualizer/modules/surfaces/SurfaceModule.vue'))

const modules = [
  { id: 'linear', index: '01', label: 'Linear Transform', caption: 'Matrix state → grid, basis, area and eigendirections', formula: 'x(t)=A(t)x', engine: 'Canvas / MathBox' },
  { id: 'complex', index: '02', label: 'Complex Mapping', caption: 'Dual planes, draggable points and domain coloring', formula: 'w=f(z)', engine: 'CindyGL / Canvas' },
  { id: 'fourier', index: '03', label: 'Fourier', caption: 'Signal, complex wrapping, integral and spectrum', formula: 'f(t)e^{-iωt}', engine: 'Canvas / FFT' },
  { id: 'laplace', index: '04', label: 'Laplace', caption: 'Decay, rotation and transform value across the s-plane', formula: '∫f(t)e^{-st}dt', engine: 'Canvas / math.js' },
  { id: 'surface', index: '05', label: '3D Surface', caption: 'Precise surfaces with orbit, wireframe and fallback', formula: 'z=f(x,y)', engine: 'Three / MathBox / Canvas' },
] as const
const selected = ref<MathModuleId | null>(null)
const mode = ref<QualityMode>('auto')
const capabilities = detectCapabilities()
const adaptiveProfile = ref<QualityProfile | null>(null)
const profile = computed(() => adaptiveProfile.value || resolveQuality(mode.value, capabilities))
const telemetry = ref<RendererTelemetry | null>(null)
const renderer = ref<RendererId | null>(null)
const activeLaunch = ref<FormulaLaunchRequest | null>(null)
let manager = new PerformanceManager(profile.value, true)

const selectedMeta = computed(() => modules.find((item) => item.id === selected.value))
const selectedComponent = computed(() => ({ linear: LinearTransformModule, complex: ComplexMappingModule, fourier: FourierModule, laplace: LaplaceModule, surface: SurfaceModule }[selected.value || 'linear']))
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

function openModule(id: MathModuleId) { activeLaunch.value = null; selected.value = id; telemetry.value = null; renderer.value = null }
function closeModule() { activeLaunch.value = null; selected.value = null; telemetry.value = null; renderer.value = null }
onBeforeUnmount(() => { selected.value = null })
</script>

<template>
  <div class="math-lab-shell">
    <header class="math-lab-header">
      <div class="math-lab-title"><span>MATH LAB / ISOLATED WORKSPACE</span><h1>{{ selectedMeta?.label || 'Interactive mathematics' }}</h1><p>{{ selectedMeta?.caption || 'Choose a mathematical system. Heavy renderers remain unloaded until a module opens.' }}</p></div>
      <div class="math-lab-system"><PerformanceSelector v-model="mode" :resolved-tier="profile.tier" /><button v-if="selected" type="button" class="math-back-button" @click="closeModule">ALL MODULES</button></div>
    </header>

    <template v-if="!selected">
      <section class="math-lab-gateway panel">
        <div class="math-gateway-status"><i /><span>VISUALIZATION KERNEL</span><b>STANDBY</b></div>
        <div><strong>No renderer is running.</strong><p>CindyGL, MathBox, Three.js, math.js and FFT are split into asynchronous chunks. Select one module to initialize only its required path.</p></div>
        <dl><div><dt>WEBGPU</dt><dd>{{ capabilities.webgpu ? 'DETECTED' : 'FALLBACK' }}</dd></div><div><dt>WEBGL2</dt><dd>{{ capabilities.webgl2 ? 'READY' : 'UNAVAILABLE' }}</dd></div><div><dt>REDUCED MOTION</dt><dd>{{ capabilities.reducedMotion ? 'ON' : 'OFF' }}</dd></div></dl>
      </section>
      <section class="math-module-grid">
        <button v-for="item in modules" :key="item.id" type="button" class="math-module-card" @click="openModule(item.id)">
          <span>{{ item.index }}</span><div><small>{{ item.engine }}</small><h2>{{ item.label }}</h2><p>{{ item.caption }}</p><code>{{ item.formula }}</code></div><b>ENTER →</b>
        </button>
      </section>
    </template>

    <template v-else>
      <section class="math-workspace-status"><span><i />{{ renderer ? `${renderer.toUpperCase()} ACTIVE` : 'STARTING RENDERER' }}</span><span>{{ profile.surfaceResolution }}² SURFACE · {{ profile.complexResolution }} COMPLEX · DPR {{ profile.maxDpr }}</span></section>
      <section v-if="activeLaunch" class="math-import-banner"><div><span>MARKDOWN FORMULA / ROUTED TO {{ selectedMeta?.label.toUpperCase() }}</span><code>{{ activeLaunch.expression }}</code></div><b>{{ activeLaunch.automatic ? `${activeLaunch.confidence.toUpperCase()} AUTO MATCH` : 'MANUAL ROUTE' }}</b></section>
      <Suspense><component :is="selectedComponent" :key="`${selected}-${activeLaunch?.id || 0}`" :profile="profile" :capabilities="capabilities" :initial-expression="routedExpression" @renderer="renderer = $event" @telemetry="receiveTelemetry" /><template #fallback><div class="math-module-loader panel"><i /><b>LOADING {{ selectedMeta?.label.toUpperCase() }}</b><span>Heavy code is requested only now.</span></div></template></Suspense>
      <RendererDebugPanel :telemetry="telemetry" :profile="profile" :capabilities="capabilities" />
    </template>
  </div>
</template>
