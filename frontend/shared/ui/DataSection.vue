<script setup lang="ts">
defineProps<{heading:string;description?:string}>()
</script>
<template><section class="ui-data-section"><header><div><h2>{{ heading }}</h2><p v-if="description">{{ description }}</p></div><slot name="actions"/></header><slot/></section></template>
