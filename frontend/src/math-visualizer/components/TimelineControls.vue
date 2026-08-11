<script setup lang="ts">
defineProps<{ progress: number; playing: boolean; speed: number; direction: 1 | -1; loop: boolean; reducedMotion?: boolean }>()
defineEmits<{ play: []; pause: []; reset: []; seek: [value: number]; speed: [value: number]; reverse: []; loop: [value: boolean] }>()
</script>

<template>
  <div class="math-timeline-controls">
    <button type="button" :disabled="reducedMotion" @click="playing ? $emit('pause') : $emit('play')">{{ playing ? 'PAUSE' : 'PLAY' }}</button>
    <button type="button" @click="$emit('reset')">RESET</button>
    <button type="button" :class="{ active: direction === -1 }" @click="$emit('reverse')">{{ direction === 1 ? 'FORWARD' : 'REVERSE' }}</button>
    <button type="button" :class="{ active: loop }" @click="$emit('loop', !loop)">LOOP {{ loop ? 'ON' : 'OFF' }}</button>
    <select :value="speed" aria-label="Animation speed" @change="$emit('speed', Number(($event.target as HTMLSelectElement).value))"><option :value=".25">0.25×</option><option :value=".5">0.5×</option><option :value="1">1×</option><option :value="2">2×</option></select>
    <input :value="progress" type="range" min="0" max="1" step="0.001" aria-label="Animation progress" @input="$emit('seek', Number(($event.target as HTMLInputElement).value))" />
    <span>{{ Math.round(progress * 100) }}%</span>
  </div>
</template>
