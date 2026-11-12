<script setup lang="ts">
withDefaults(defineProps<{kind?:'empty'|'no-results'|'error'|'forbidden';title:string;detail?:string}>(),{kind:'empty'})
</script>
<template><div class="ui-empty-state" :role="kind==='error'?'alert':'status'"><strong>{{ title }}</strong><p v-if="detail">{{ detail }}</p><slot/></div></template>
