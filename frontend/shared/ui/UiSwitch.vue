<script setup lang="ts">
defineProps<{label:string;checked:boolean;disabled?:boolean}>();defineEmits<{'update:checked':[value:boolean]}>()
</script>
<template><label class="ui-selection-row"><span>{{ label }}</span><input type="checkbox" role="switch" :checked="checked" :disabled="disabled" @change="$emit('update:checked',($event.target as HTMLInputElement).checked)"></label></template>
