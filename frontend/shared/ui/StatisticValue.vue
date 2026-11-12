<script setup lang="ts">
defineProps<{value:string|number;label:string;unit?:string;state?:string}>()
</script>
<template><div class="ui-statistic-value"><small>{{ label }}</small><strong>{{ value }}<small v-if="unit"> {{ unit }}</small></strong></div></template>
