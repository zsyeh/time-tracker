<script setup lang="ts">
function openNavigation(){window.dispatchEvent(new Event('learning:open-navigation'))}
defineProps<{
  title: string
  metadata?: string
  context?: string
}>()
</script>

<template>
  <header class="application-page-header">
    <button type="button" class="application-page-navigation ui-icon-button" aria-label="打开导航" @click="openNavigation"><svg viewBox="0 0 20 20" fill="none" stroke="currentColor" aria-hidden="true"><path d="M3 5h14M3 10h14M3 15h14"/></svg></button><div class="application-page-title"><span v-if="context" class="application-page-context">{{ context }} /</span><h1>{{ title }}</h1><span v-if="metadata">{{ metadata }}</span><slot name="metadata" /></div>
    <div v-if="$slots.actions" class="application-page-actions"><slot name="actions" /></div>
  </header>
</template>

<style>.application-page-navigation{display:none;flex:none}.sidebar-collapsed .application-page-navigation{display:grid}.application-page-title{min-width:0;flex:1}@media(max-width:899px){.application-page-navigation{display:grid}.main-content,.sidebar-collapsed .main-content{padding-top:env(safe-area-inset-top,0px)}.application-page-header{padding-left:12px}}</style>
