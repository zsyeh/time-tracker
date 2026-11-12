<script setup lang="ts">
import { typeLabel } from '../lib/examTypes'
defineProps<{ type?: string; group?: string }>()
</script>
<template><small class="exam-type-badge" :class="`exam-${group || type || 'unknown'}`">{{ typeLabel(type || 'unknown') }}</small></template>
<style scoped>
.exam-type-badge { display:inline-flex; align-items:center; gap:5px; font-size:12px; font-weight:500; line-height:1.5; color:var(--text-secondary); white-space:nowrap; }
.exam-type-badge::before { content:''; width:6px; height:6px; border-radius:50%; background:var(--text-tertiary,var(--text-secondary)); flex-shrink:0; }
.exam-small::before,.exam-choice::before,.exam-fill::before,.exam-judgment::before { background:var(--format-small); }
.exam-large::before { background:var(--format-large); }
.exam-short_answer::before { background:var(--format-short-answer); }
</style>
