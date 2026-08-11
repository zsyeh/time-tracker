<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { computeSpectrum } from '../../core/fft'
import { fourierCoefficient } from '../../core/numerics'
import { useMathTimeline } from '../../core/useMathTimeline'
import MathFormula from '../../components/MathFormula.vue'
import TimelineControls from '../../components/TimelineControls.vue'
import VisualizationViewport from '../../components/VisualizationViewport.vue'
import type { FourierScene, QualityProfile, RendererId, RendererTelemetry, RuntimeCapabilities, SignalPreset } from '../../types'

const props = defineProps<{ profile: QualityProfile; capabilities: RuntimeCapabilities; initialExpression?: string }>()
const emit = defineEmits<{ telemetry: [value: RendererTelemetry]; renderer: [id: RendererId] }>()
const viewport = ref<InstanceType<typeof VisualizationViewport> | null>(null)
const preset = ref<SignalPreset>('two-tone')
const omega = ref(2)
const options = reactive({ wrapping: true, spectrum: true })
const error = ref('')
const spectrum = ref<number[]>(computeSpectrum(preset.value))
watch(preset, (value) => { spectrum.value = computeSpectrum(value) })
watch(() => props.initialExpression, (source) => {
  if (!source) return
  const value = source.toLowerCase()
  preset.value = value.includes('square') ? 'square' : value.includes('triangle') ? 'triangle' : /sin|cos/.test(value) ? 'sine' : 'two-tone'
}, { immediate: true })
const scene = computed<FourierScene>(() => ({ kind: 'fourier', preset: preset.value, omega: omega.value, showWrapping: options.wrapping, showSpectrum: options.spectrum, spectrum: spectrum.value }))
const coefficient = computed(() => fourierCoefficient(preset.value, omega.value, 1024))
const timeline = useMathTimeline((value) => { omega.value = .25 + value * 11.75; viewport.value?.setTime(value) }, props.capabilities.reducedMotion)
</script>

<template>
  <div class="math-module-layout">
    <aside class="math-module-controls">
      <label class="math-field"><span class="math-control-label">SIGNAL</span><el-select v-model="preset"><el-option label="Single sine" value="sine" /><el-option label="Two-tone" value="two-tone" /><el-option label="Square wave" value="square" /><el-option label="Triangle wave" value="triangle" /></el-select></label>
      <label class="math-field"><span class="math-control-label">FREQUENCY ω · {{ omega.toFixed(2) }}</span><el-slider v-model="omega" :min=".25" :max="12" :step=".05" /></label>
      <div class="math-switches"><el-checkbox v-model="options.wrapping">Complex wrapping</el-checkbox><el-checkbox v-model="options.spectrum">Frequency response</el-checkbox></div>
      <dl class="math-result-list"><div><dt>REAL</dt><dd>{{ coefficient.re.toFixed(5) }}</dd></div><div><dt>IMAGINARY</dt><dd>{{ coefficient.im.toFixed(5) }}</dd></div><div><dt>MAGNITUDE</dt><dd>{{ Math.hypot(coefficient.re, coefficient.im).toFixed(5) }}</dd></div><div><dt>PHASE</dt><dd>{{ Math.atan2(coefficient.im, coefficient.re).toFixed(4) }}</dd></div></dl>
    </aside>
    <section class="math-module-stage">
      <VisualizationViewport ref="viewport" :scene="scene" :profile="profile" :capabilities="capabilities" @renderer="emit('renderer', $event)" @telemetry="emit('telemetry', $event)" @error="error = $event" />
      <TimelineControls :progress="timeline.progress.value" :playing="timeline.playing.value" :speed="timeline.speed.value" :direction="timeline.direction.value" :loop="timeline.loop.value" :reduced-motion="capabilities.reducedMotion" @play="timeline.play" @pause="timeline.pause" @reset="timeline.reset" @seek="timeline.seek" @speed="timeline.setSpeed" @reverse="timeline.reverse" @loop="timeline.setLoop" />
      <MathFormula source="F(\omega)=\int_0^1 f(t)e^{-i2\pi\omega t}\,dt" />
      <p v-if="error" class="math-module-error">{{ error }}</p>
    </section>
  </div>
</template>
