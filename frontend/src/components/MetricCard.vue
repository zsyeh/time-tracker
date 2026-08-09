<script setup lang="ts">
defineProps<{
  label: string
  value: string | number
  suffix?: string
  tone?: 'default' | 'goal' | 'warm' | 'blue'
  hint?: string
}>()
</script>

<template>
  <article class="metric-card" :class="`metric-${tone || 'default'}`">
    <p>{{ label }}</p>
    <div><strong>{{ value }}</strong><span v-if="suffix">{{ suffix }}</span></div>
    <small v-if="hint">{{ hint }}</small>
  </article>
</template>
