<script setup lang="ts">
import type { QualityProfile, RendererTelemetry, RuntimeCapabilities } from '../types'
defineProps<{ telemetry: RendererTelemetry | null; profile: QualityProfile; capabilities: RuntimeCapabilities }>()
</script>

<template>
  <details class="math-debug-panel"><summary>Renderer details</summary><dl><div><dt>RENDERER</dt><dd>{{ telemetry?.renderer || 'loading' }}</dd></div><div><dt>TIER</dt><dd>{{ profile.tier }}</dd></div><div><dt>VIEWPORT</dt><dd>{{ telemetry ? `${telemetry.width}×${telemetry.height} @${telemetry.dpr}` : '—' }}</dd></div><div><dt>FRAME</dt><dd>{{ telemetry ? `${telemetry.frameTime.toFixed(1)} ms` : '—' }}</dd></div><div><dt>WEBGL2</dt><dd>{{ capabilities.webgl2 ? 'yes' : 'no' }}</dd></div><div><dt>WEBGPU</dt><dd>{{ capabilities.webgpu ? 'detected' : 'no' }}</dd></div></dl></details>
</template>
