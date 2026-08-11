<script setup lang="ts">
import { computed } from 'vue'
import { formulaModuleOptions } from '../math-visualizer/core/formulaRouter'
import type { MathModuleId } from '../math-visualizer/types'

const props = defineProps<{ expression: string; detected: MathModuleId; confidence: 'high' | 'medium' | 'low'; selected: MathModuleId }>()
const emit = defineEmits<{ close: []; open: []; 'update:selected': [value: MathModuleId] }>()
const detectedLabel = computed(() => formulaModuleOptions.find((item) => item.id === props.detected)?.label || props.detected)
</script>

<template>
  <div class="formula-router-overlay" role="presentation" @click.self="emit('close')">
    <section class="formula-router-panel" role="dialog" aria-modal="true" aria-label="Choose a mathematical visualization">
      <header><div><span>FORMULA ROUTER / MATH LAB</span><h2>Visualize this formula</h2></div><button type="button" aria-label="Close formula router" @click="emit('close')">×</button></header>
      <div class="formula-router-detection"><span>AUTO-DETECTED</span><strong>{{ detectedLabel }}</strong><b>{{ confidence.toUpperCase() }} CONFIDENCE</b></div>
      <code>{{ expression }}</code>
      <label><span>VISUALIZATION SYSTEM</span><select :value="selected" @change="emit('update:selected', ($event.target as HTMLSelectElement).value as MathModuleId)"><option v-for="option in formulaModuleOptions" :key="option.id" :value="option.id">{{ option.label }}</option></select></label>
      <p>Automatic routing is only a starting point. Change the system when the same notation has a different mathematical meaning.</p>
      <footer><button type="button" @click="emit('close')">CANCEL</button><button type="button" class="formula-router-open" @click="emit('open')">OPEN VISUALIZATION →</button></footer>
    </section>
  </div>
</template>
