<script setup lang="ts">
defineProps<{label:string;id?:string;options:{value:string;label:string}[];modelValue:string;disabled?:boolean}>();defineEmits<{'update:modelValue':[value:string]}>()
</script>
<template><label><span>{{ label }}</span><select :id="id" class="ui-field" :value="modelValue" :disabled="disabled" @change="$emit('update:modelValue',($event.target as HTMLSelectElement).value)"><option v-for="item in options" :key="item.value" :value="item.value">{{ item.label }}</option></select></label></template>
