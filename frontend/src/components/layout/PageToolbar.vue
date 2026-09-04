<script setup lang="ts">
withDefaults(defineProps<{ label?: string }>(), { label: 'Page controls' })
</script>

<template>
  <div class="page-toolbar" role="toolbar" :aria-label="label">
    <div class="page-toolbar-primary"><slot /></div>
    <div v-if="$slots.actions" class="page-toolbar-actions"><slot name="actions" /></div>
  </div>
</template>
