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
    <header><p>{{ label }}</p><i /></header>
    <div><strong>{{ value }}</strong><span v-if="suffix">{{ suffix }}</span></div>
    <footer v-if="hint"><small>{{ hint }}</small></footer>
  </article>
</template>
