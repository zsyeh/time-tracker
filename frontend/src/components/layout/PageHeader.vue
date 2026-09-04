<script setup lang="ts">
defineProps<{
  title: string
  metadata?: string
  context?: string
}>()
</script>

<template>
  <header class="application-page-header">
    <div class="application-page-title"><span v-if="context" class="application-page-context">{{ context }} /</span><h1>{{ title }}</h1><span v-if="metadata">{{ metadata }}</span><slot name="metadata" /></div>
    <div v-if="$slots.actions" class="application-page-actions"><slot name="actions" /></div>
  </header>
</template>
