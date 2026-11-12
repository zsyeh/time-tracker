<script setup lang="ts">
withDefaults(defineProps<{label?:string}>(),{label:'正在加载…'})
</script>
<template><div class="ui-empty-state" role="status" aria-busy="true">{{ label }}</div></template>
