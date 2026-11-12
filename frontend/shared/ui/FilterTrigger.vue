<script setup lang="ts">
withDefaults(defineProps<{count?:number;open?:boolean;label?:string}>(),{count:0,open:false,label:'筛选'});defineEmits<{click:[]}>()
</script>
<template><button type="button" class="ui-button ui-button--secondary" :aria-expanded="open" @click="$emit('click')">{{ label }}<span v-if="count">({{ count }})</span></button></template>
