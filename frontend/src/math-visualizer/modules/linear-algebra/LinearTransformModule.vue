<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { determinant, eigenDirections, transform } from '../../core/numerics'
import { matrixFromFormula } from '../../core/formulaRouter'
import { useMathTimeline } from '../../core/useMathTimeline'
import MathFormula from '../../components/MathFormula.vue'
import TimelineControls from '../../components/TimelineControls.vue'
import VisualizationViewport from '../../components/VisualizationViewport.vue'
import type { LinearScene, QualityProfile, RendererId, RendererTelemetry, RuntimeCapabilities } from '../../types'

const props = defineProps<{ profile: QualityProfile; capabilities: RuntimeCapabilities; initialExpression?: string }>()
const emit = defineEmits<{ telemetry: [value: RendererTelemetry]; renderer: [id: RendererId] }>()
const viewport = ref<InstanceType<typeof VisualizationViewport> | null>(null)
const matrix = reactive({ a: 1.2, b: .8, c: -.35, d: 1.55 })
const vector = reactive({ x: 2, y: 1 })
const options = reactive({ grid: true, square: true, eigen: true })
const error = ref('')
const scene = computed<LinearScene>(() => ({ kind: 'linear', matrix: [matrix.a, matrix.b, matrix.c, matrix.d], vector: [vector.x, vector.y], showGrid: options.grid, showSquare: options.square, showEigenvectors: options.eigen }))
const det = computed(() => determinant(scene.value.matrix))
const mapped = computed(() => transform(scene.value.matrix, scene.value.vector))
const eigen = computed(() => eigenDirections(scene.value.matrix))
const timeline = useMathTimeline((value) => viewport.value?.setTime(value), props.capabilities.reducedMotion)
watch(() => props.initialExpression, (source) => {
  const values = source ? matrixFromFormula(source) : null
  if (values) [matrix.a, matrix.b, matrix.c, matrix.d] = values
}, { immediate: true })
function resetMatrix() { Object.assign(matrix, { a: 1.2, b: .8, c: -.35, d: 1.55 }); Object.assign(vector, { x: 2, y: 1 }); timeline.reset() }
</script>

<template>
  <div class="math-module-layout">
    <aside class="math-module-controls">
      <div><span class="math-control-label">MATRIX A</span><div class="matrix-inputs"><el-input-number v-model="matrix.a" :step=".1" :precision="2" controls-position="right" /><el-input-number v-model="matrix.b" :step=".1" :precision="2" controls-position="right" /><el-input-number v-model="matrix.c" :step=".1" :precision="2" controls-position="right" /><el-input-number v-model="matrix.d" :step=".1" :precision="2" controls-position="right" /></div></div>
      <div><span class="math-control-label">VECTOR v</span><div class="math-control-pair"><el-input-number v-model="vector.x" :step=".1" :precision="2" /><el-input-number v-model="vector.y" :step=".1" :precision="2" /></div></div>
      <div class="math-switches"><el-checkbox v-model="options.grid">Grid</el-checkbox><el-checkbox v-model="options.square">Unit square</el-checkbox><el-checkbox v-model="options.eigen">Eigendirections</el-checkbox></div>
      <button type="button" class="math-reset-button" @click="resetMatrix">RESET SCENE</button>
      <dl class="math-result-list"><div><dt>DETERMINANT</dt><dd>{{ det.toFixed(4) }}</dd></div><div><dt>Av</dt><dd>[{{ mapped[0].toFixed(2) }}, {{ mapped[1].toFixed(2) }}]</dd></div><div><dt>ORIENTATION</dt><dd>{{ det < 0 ? 'FLIPPED' : 'PRESERVED' }}</dd></div><div><dt>REAL EIGENDIRS</dt><dd>{{ eigen.length }}</dd></div></dl>
    </aside>
    <section class="math-module-stage">
      <VisualizationViewport ref="viewport" :scene="scene" :profile="profile" :capabilities="capabilities" @renderer="emit('renderer', $event)" @telemetry="emit('telemetry', $event)" @error="error = $event" />
      <TimelineControls :progress="timeline.progress.value" :playing="timeline.playing.value" :speed="timeline.speed.value" :direction="timeline.direction.value" :loop="timeline.loop.value" :reduced-motion="capabilities.reducedMotion" @play="timeline.play" @pause="timeline.pause" @reset="timeline.reset" @seek="timeline.seek" @speed="timeline.setSpeed" @reverse="timeline.reverse" @loop="timeline.setLoop" />
      <MathFormula source="A(t)=(1-t)I+tA,\qquad x(t)=A(t)x" />
      <p v-if="error" class="math-module-error">{{ error }}</p>
    </section>
  </div>
</template>
