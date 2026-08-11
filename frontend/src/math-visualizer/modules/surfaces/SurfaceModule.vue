<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useMathTimeline } from '../../core/useMathTimeline'
import MathFormula from '../../components/MathFormula.vue'
import TimelineControls from '../../components/TimelineControls.vue'
import VisualizationViewport from '../../components/VisualizationViewport.vue'
import type { QualityProfile, RendererId, RendererTelemetry, RuntimeCapabilities, SurfacePreset, SurfaceScene } from '../../types'

const props = defineProps<{ profile: QualityProfile; capabilities: RuntimeCapabilities }>()
const emit = defineEmits<{ telemetry: [value: RendererTelemetry]; renderer: [id: RendererId] }>()
const viewport = ref<InstanceType<typeof VisualizationViewport> | null>(null)
const presets: Array<{ id: SurfacePreset; label: string; expression: string }> = [
  { id: 'ripple', label: 'Radial ripple', expression: '\\frac{\\sin(x^2+y^2)}{1+0.12(x^2+y^2)}' },
  { id: 'saddle', label: 'Hyperbolic paraboloid', expression: '0.22(x^2-y^2)' },
  { id: 'gaussian', label: 'Gaussian bell', expression: '2.2e^{-0.35(x^2+y^2)}' },
  { id: 'waves', label: 'Product wave', expression: '\\sin(x)\\cos(y)' },
]
const preset = ref<SurfacePreset>('ripple')
const wireframe = ref(false)
const autoRotate = ref(false)
const error = ref('')
const expressionError = ref('')
const customExpression = ref('sin(sqrt(x^2 + y^2)) / (1 + 0.1 * (x^2 + y^2))')
const customSurface = ref<SurfaceScene['sampleGrid']>()
const applying = ref(false)
const selected = computed(() => presets.find((item) => item.id === preset.value)!)
const activeExpression = computed(() => customSurface.value ? customExpression.value : selected.value.expression)
const scene = computed<SurfaceScene>(() => ({ kind: 'surface', preset: preset.value, expression: `z = ${activeExpression.value}`, wireframe: wireframe.value, autoRotate: autoRotate.value, sampleGrid: customSurface.value }))
const timeline = useMathTimeline((value) => viewport.value?.setTime(value), props.capabilities.reducedMotion)
watch(preset, () => { customSurface.value = undefined; expressionError.value = '' })
async function applyCustomExpression() {
  applying.value = true
  expressionError.value = ''
  try {
    const { MathEngine } = await import('../../core/MathEngine')
    customSurface.value = await new MathEngine().sampleSurface(customExpression.value, 65, 5)
  } catch (reason) {
    expressionError.value = (reason as Error).message
  } finally {
    applying.value = false
  }
}
</script>

<template>
  <div class="math-module-layout">
    <aside class="math-module-controls">
      <label class="math-field"><span class="math-control-label">SURFACE z=f(x,y)</span><el-select v-model="preset"><el-option v-for="item in presets" :key="item.id" :label="item.label" :value="item.id" /></el-select></label>
      <div class="math-expression-control"><span class="math-control-label">SAFE CUSTOM EXPRESSION</span><el-input v-model="customExpression" maxlength="180" placeholder="sin(x) * cos(y)" /><button type="button" class="math-reset-button" :disabled="applying" @click="applyCustomExpression">{{ applying ? 'SAMPLING…' : 'APPLY EXPRESSION' }}</button><small>Parsed through an AST allowlist. No JavaScript evaluation.</small><p v-if="expressionError" class="math-inline-error">{{ expressionError }}</p></div>
      <div class="math-switches"><el-checkbox v-model="wireframe">Wireframe</el-checkbox><el-checkbox v-model="autoRotate" :disabled="capabilities.reducedMotion">Auto rotate</el-checkbox></div>
      <p class="math-gesture-note">Drag to orbit in GPU modes. Wheel or two-finger gesture changes the view. Compatibility mode uses a CPU wireframe projection.</p>
      <dl class="math-result-list"><div><dt>DISPLAY GRID</dt><dd>{{ profile.surfaceResolution }}²</dd></div><div><dt>BACKEND</dt><dd>{{ profile.tier === 'high' ? 'MODERN THREE' : profile.tier === 'balanced' ? 'MATHBOX' : 'CANVAS' }}</dd></div><div><dt>ANTIALIAS</dt><dd>{{ profile.enableAntialias ? 'ON' : 'OFF' }}</dd></div></dl>
    </aside>
    <section class="math-module-stage">
      <VisualizationViewport ref="viewport" :scene="scene" :profile="profile" :capabilities="capabilities" @renderer="emit('renderer', $event)" @telemetry="emit('telemetry', $event)" @error="error = $event" />
      <TimelineControls :progress="timeline.progress.value" :playing="timeline.playing.value" :speed="timeline.speed.value" :direction="timeline.direction.value" :loop="timeline.loop.value" :reduced-motion="capabilities.reducedMotion || !autoRotate" @play="timeline.play" @pause="timeline.pause" @reset="timeline.reset" @seek="timeline.seek" @speed="timeline.setSpeed" @reverse="timeline.reverse" @loop="timeline.setLoop" />
      <MathFormula :source="`z=${activeExpression}`" />
      <p v-if="error" class="math-module-error">{{ error }}</p>
    </section>
  </div>
</template>
