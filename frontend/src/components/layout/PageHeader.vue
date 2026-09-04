<script setup lang="ts">
defineProps<{
  title: string
  metadata?: string
}>()
</script>

<template>
  <header class="application-page-header">
    <div class="application-page-title"><h1>{{ title }}</h1><span v-if="metadata">{{ metadata }}</span><slot name="metadata" /></div>
    <div v-if="$slots.actions" class="application-page-actions"><slot name="actions" /></div>
  </header>
</template>
