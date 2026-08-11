<script setup lang="ts">
import { computed } from 'vue'
import katex from 'katex'
import 'katex/dist/katex.min.css'

const props = defineProps<{ source: string; display?: boolean }>()
const html = computed(() => katex.renderToString(props.source, { displayMode: props.display ?? true, output: 'htmlAndMathml', strict: 'warn', throwOnError: false, trust: false }))
</script>

<template><div class="math-lab-formula" v-html="html" /></template>
