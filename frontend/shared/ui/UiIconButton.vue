<script setup lang="ts">

withDefaults(defineProps<{label:string;pressed?:boolean;disabled?:boolean;busy?:boolean}>(),{disabled:false,busy:false})

</script>
<template><button type="button" class="ui-icon-button" :aria-label="label" :title="label" :aria-pressed="pressed" :disabled="disabled || busy" :aria-busy="busy || undefined"><slot/></button></template>
