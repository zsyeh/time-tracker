<script setup lang="ts">
defineProps<{title:string;subtitle?:string;navToggle?:boolean}>();defineEmits<{toggle:[]}>()
</script>
<template><header class="ui-app-header"><button v-if="navToggle" type="button" class="ui-icon-button" aria-label="打开导航" @click="$emit('toggle')"><svg viewBox="0 0 20 20" fill="none" stroke="currentColor"><path d="M3 5h14M3 10h14M3 15h14"/></svg></button><strong>{{ title }}</strong><span v-if="subtitle">{{ subtitle }}</span><div><slot name="actions"/></div></header></template>
<style scoped>.ui-app-header{display:flex;align-items:center;gap:12px;min-height:48px;padding:4px 16px;background:var(--surface-page)}.ui-app-header strong{font-size:14px;font-weight:600}.ui-app-header>span{font-size:13px;color:var(--text-secondary)}.ui-app-header>div{margin-left:auto}@media(pointer:coarse){.ui-app-header{min-height:52px}}</style>
