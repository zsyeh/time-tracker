<script setup lang="ts">
import type { QualityMode, QualityTier } from '../types'

defineProps<{ modelValue: QualityMode; resolvedTier: QualityTier }>()
defineEmits<{ 'update:modelValue': [value: QualityMode] }>()
const modes: Array<{ id: QualityMode; label: string }> = [
  { id: 'auto', label: 'Auto' }, { id: 'compatibility', label: 'Compatibility' },
  { id: 'low', label: 'Low' }, { id: 'balanced', label: 'Balanced' }, { id: 'high', label: 'High' },
]
</script>

<template>
  <label class="math-quality-selector"><span>PERFORMANCE</span><select :value="modelValue" @change="$emit('update:modelValue', ($event.target as HTMLSelectElement).value as QualityMode)"><option v-for="mode in modes" :key="mode.id" :value="mode.id">{{ mode.label }}</option></select><b>{{ resolvedTier.toUpperCase() }}</b></label>
</template>
