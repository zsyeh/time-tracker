<script setup lang="ts">
import { computed, ref } from 'vue'
import { numericalLaplace } from '../../core/numerics'
import { useMathTimeline } from '../../core/useMathTimeline'
import MathFormula from '../../components/MathFormula.vue'
import TimelineControls from '../../components/TimelineControls.vue'
import VisualizationViewport from '../../components/VisualizationViewport.vue'
import type { LaplacePreset, LaplaceScene, QualityProfile, RendererId, RendererTelemetry, RuntimeCapabilities } from '../../types'

const props = defineProps<{ profile: QualityProfile; capabilities: RuntimeCapabilities }>()
const emit = defineEmits<{ telemetry: [value: RendererTelemetry]; renderer: [id: RendererId] }>()
const viewport = ref<InstanceType<typeof VisualizationViewport> | null>(null)
const preset = ref<LaplacePreset>('sine')
const sigma = ref(1)
const omega = ref(2)
const error = ref('')
const scene = computed<LaplaceScene>(() => ({ kind: 'laplace', preset: preset.value, sigma: sigma.value, omega: omega.value }))
const result = computed(() => numericalLaplace(preset.value, sigma.value, omega.value, 12, 2400))
const timeline = useMathTimeline((value) => { omega.value = -5 + value * 10; viewport.value?.setTime(value) }, props.capabilities.reducedMotion)
</script>

<template>
  <div class="math-module-layout">
    <aside class="math-module-controls">
      <label class="math-field"><span class="math-control-label">SIGNAL f(t)</span><el-select v-model="preset"><el-option label="1" value="constant" /><el-option label="exp(0.7t)" value="exponential" /><el-option label="sin(2t)" value="sine" /><el-option label="Unit pulse" value="pulse" /></el-select></label>
      <label class="math-field"><span class="math-control-label">REAL PART σ · {{ sigma.toFixed(2) }}</span><el-slider v-model="sigma" :min=".1" :max="4" :step=".05" /></label>
      <label class="math-field"><span class="math-control-label">IMAGINARY PART ω · {{ omega.toFixed(2) }}</span><el-slider v-model="omega" :min="-5" :max="5" :step=".05" /></label>
      <p class="math-gesture-note">The integral is numerically sampled. Display quality changes geometry density, not the reported transform precision.</p>
      <dl class="math-result-list"><div><dt>Re F(s)</dt><dd>{{ result.re.toFixed(5) }}</dd></div><div><dt>Im F(s)</dt><dd>{{ result.im.toFixed(5) }}</dd></div><div><dt>|F(s)|</dt><dd>{{ Math.hypot(result.re, result.im).toFixed(5) }}</dd></div></dl>
    </aside>
    <section class="math-module-stage">
      <VisualizationViewport ref="viewport" :scene="scene" :profile="profile" :capabilities="capabilities" @renderer="emit('renderer', $event)" @telemetry="emit('telemetry', $event)" @error="error = $event" />
      <TimelineControls :progress="timeline.progress.value" :playing="timeline.playing.value" :speed="timeline.speed.value" :direction="timeline.direction.value" :loop="timeline.loop.value" :reduced-motion="capabilities.reducedMotion" @play="timeline.play" @pause="timeline.pause" @reset="timeline.reset" @seek="timeline.seek" @speed="timeline.setSpeed" @reverse="timeline.reverse" @loop="timeline.setLoop" />
      <MathFormula source="F(s)=\int_0^\infty f(t)e^{-st}\,dt,\qquad s=\sigma+i\omega" />
      <p v-if="error" class="math-module-error">{{ error }}</p>
    </section>
  </div>
</template>
