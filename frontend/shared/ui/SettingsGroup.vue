<script setup lang="ts">
defineProps<{title:string;description?:string}>()
</script>
<template><section class="ui-settings-group"><h2>{{ title }}</h2><p v-if="description" class="settings-description">{{ description }}</p><div class="ui-settings-group-body"><slot/></div></section></template>
<style scoped>.settings-description{margin:0 0 12px;color:var(--text-secondary);font-size:13px}</style>
