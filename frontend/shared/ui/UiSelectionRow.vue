<script setup lang="ts">

withDefaults(defineProps<{label:string;description?:string;checked:boolean;mode?:'checkbox'|'radio';disabled?:boolean;name?:string;meta?:string}>(),{mode:'checkbox',disabled:false})
defineEmits<{'update:checked':[value:boolean]}>()

</script>
<template><label class="ui-selection-row"><input :type="mode" :name="name" :checked="checked" :disabled="disabled" @change="$emit('update:checked',($event.target as HTMLInputElement).checked)"><span>{{ label }}<span v-if="description" class="ui-selection-row-description">{{ description }}</span></span><small v-if="meta">{{ meta }}</small></label></template>
