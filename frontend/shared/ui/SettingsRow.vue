<script setup lang="ts">

withDefaults(defineProps<{label:string;description?:string;value?:string;href?:string;kind?:'value'|'link'|'select'|'switch'|'action';disabled?:boolean}>(),{kind:'value',disabled:false})

</script>
<template><component :is="href?'a':kind==='action'?'button':'div'" class="ui-settings-row" :href="href" :type="kind==='action'?'button':undefined" :disabled="kind==='action'?disabled:undefined"><span><span>{{ label }}</span><small v-if="description" class="ui-selection-row-description">{{ description }}</small></span><span class="ui-settings-row-value"><slot><span>{{ value }}</span></slot><span v-if="href" aria-hidden="true"> ›</span></span></component></template>
