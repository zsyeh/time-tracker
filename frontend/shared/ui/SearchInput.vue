<script setup lang="ts">
withDefaults(defineProps<{modelValue:string;label:string;busy?:boolean;error?:string}>(),{busy:false})
defineEmits<{'update:modelValue':[value:string];commit:[];clear:[]}>()
</script>
<template><label class="ui-search-input"><span class="sr-only">{{ label }}</span><input type="search" class="ui-field" :value="modelValue" :aria-busy="busy||undefined" :aria-invalid="!!error||undefined" :placeholder="label" @input="$emit('update:modelValue',($event.target as HTMLInputElement).value)" @keydown.enter="!$event.isComposing&&$emit('commit')"><button v-if="modelValue" type="button" class="ui-icon-button" aria-label="清除搜索" @click="$emit('update:modelValue','');$emit('clear')">×</button><small v-if="error" role="alert">{{ error }}</small></label></template>
<style scoped>.ui-search-input{position:relative;display:flex;align-items:center;min-width:0}.ui-search-input input{width:100%;padding-right:44px}.ui-search-input button{position:absolute;right:2px}.ui-search-input small{position:absolute;top:100%;color:var(--status-danger)}</style>
