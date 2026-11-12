<script setup lang="ts">
import UiMenu,{type MenuItem} from './UiMenu.vue';defineProps<{open:boolean;anchor:HTMLElement|null|{x:number;y:number};items:MenuItem[];label?:string}>();defineEmits<{'update:open':[value:boolean]}>()
</script>
<template><UiMenu :open="open" :anchor="anchor" :items="items" :label="label" @update:open="$emit('update:open',$event)"/></template>
