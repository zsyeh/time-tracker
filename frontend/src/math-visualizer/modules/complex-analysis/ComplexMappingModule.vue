<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { evaluateComplex } from '../../core/numerics'
import MathFormula from '../../components/MathFormula.vue'
import VisualizationViewport from '../../components/VisualizationViewport.vue'
import type { ComplexPreset, ComplexScene, QualityProfile, RendererId, RendererTelemetry, RuntimeCapabilities, Vec2 } from '../../types'

const props = defineProps<{ profile: QualityProfile; capabilities: RuntimeCapabilities }>()
const emit = defineEmits<{ telemetry: [value: RendererTelemetry]; renderer: [id: RendererId] }>()
const presets: Array<{ id: ComplexPreset; label: string; expression: string; note: string }> = [
  { id: 'identity', label: 'Identity', expression: 'z', note: 'Conformal baseline' }, { id: 'square', label: 'Square', expression: 'z^2', note: 'Angles double around zero' },
  { id: 'reciprocal', label: 'Reciprocal', expression: '1/z', note: 'Pole at z = 0' }, { id: 'exp', label: 'Exponential', expression: 'exp(z)', note: 'Periodic in the imaginary direction' },
  { id: 'sin', label: 'Sine', expression: 'sin(z)', note: 'Entire complex function' }, { id: 'cos', label: 'Cosine', expression: 'cos(z)', note: 'Entire complex function' },
  { id: 'log', label: 'Principal log', expression: 'log(z)', note: 'Principal branch; cut on negative real axis' },
]
const selected = ref<ComplexPreset>('square')
const point = reactive({ x: 1, y: 1 })
const options = reactive({ grid: true, domain: true })
const error = ref('')
const preset = computed(() => presets.find((item) => item.id === selected.value)!)
const scene = computed<ComplexScene>(() => ({ kind: 'complex', preset: selected.value, expression: `w = ${preset.value.expression}`, point: [point.x, point.y], showGrid: options.grid, domainColoring: options.domain }))
const mapped = computed(() => evaluateComplex(selected.value, { re: point.x, im: point.y }))
function updatePoint(value: Vec2) { point.x = value[0]; point.y = value[1] }
</script>

<template>
  <div class="math-module-layout">
    <aside class="math-module-controls">
      <label class="math-field"><span class="math-control-label">FUNCTION f(z)</span><el-select v-model="selected"><el-option v-for="item in presets" :key="item.id" :label="`${item.label} · ${item.expression}`" :value="item.id" /></el-select><small>{{ preset.note }}</small></label>
      <div><span class="math-control-label">POINT z</span><div class="math-control-pair"><el-input-number v-model="point.x" :step=".1" :precision="2" /><el-input-number v-model="point.y" :step=".1" :precision="2" /></div></div>
      <div class="math-switches"><el-checkbox v-model="options.grid">Coordinate grid</el-checkbox><el-checkbox v-model="options.domain">Domain coloring</el-checkbox></div>
      <p class="math-gesture-note">Drag inside the z-plane. Singularities are discarded instead of drawing invalid values.</p>
      <dl class="math-result-list"><div><dt>z</dt><dd>{{ point.x.toFixed(2) }} {{ point.y < 0 ? '−' : '+' }} {{ Math.abs(point.y).toFixed(2) }}i</dd></div><div><dt>f(z)</dt><dd>{{ mapped ? `${mapped.re.toFixed(3)} ${mapped.im < 0 ? '−' : '+'} ${Math.abs(mapped.im).toFixed(3)}i` : 'singular' }}</dd></div><div><dt>|f(z)|</dt><dd>{{ mapped ? Math.hypot(mapped.re, mapped.im).toFixed(3) : '∞' }}</dd></div><div><dt>arg f(z)</dt><dd>{{ mapped ? Math.atan2(mapped.im, mapped.re).toFixed(3) : '—' }}</dd></div></dl>
    </aside>
    <section class="math-module-stage">
      <VisualizationViewport :scene="scene" :profile="profile" :capabilities="capabilities" @point-change="updatePoint" @renderer="emit('renderer', $event)" @telemetry="emit('telemetry', $event)" @error="error = $event" />
      <MathFormula :source="`w=f(z)=${preset.expression.replace('^', '^')},\qquad z=${point.x.toFixed(2)}${point.y < 0 ? '' : '+'}${point.y.toFixed(2)}i`" />
      <p v-if="error" class="math-module-error">{{ error }}</p>
    </section>
  </div>
</template>
