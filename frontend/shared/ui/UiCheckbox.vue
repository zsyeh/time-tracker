<script setup lang="ts">
import UiSelectionRow from './UiSelectionRow.vue';defineProps<{label:string;checked:boolean;disabled?:boolean}>();defineEmits<{'update:checked':[value:boolean]}>()
</script>
<template><UiSelectionRow :label="label" :checked="checked" :disabled="disabled" @update:checked="$emit('update:checked',$event)"/></template>
