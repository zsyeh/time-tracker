<script setup lang="ts">

import type {Component} from 'vue'
import type {RouteLocationRaw} from 'vue-router'
defineProps<{label:string;to?:RouteLocationRaw;href?:string;icon?:Component;active?:boolean;disabled?:boolean;depth?:0|1;badge?:string|number}>()

</script>
<template><component :is="disabled?'span':href?'a':'RouterLink'" v-bind="disabled?{}:href?{href}:{to}" class="ui-navigation-item" :class="{active,'is-disabled':disabled}" :aria-current="active?'page':undefined" :aria-disabled="disabled||undefined"><component v-if="icon" :is="icon" aria-hidden="true"/><span>{{ label }}</span><small v-if="badge!==undefined">{{ badge }}</small></component></template>
<style scoped>.ui-navigation-item{display:flex;align-items:center;gap:8px;min-height:36px;padding:8px 10px;border:0;border-radius:6px;color:var(--text-secondary);text-decoration:none;font-size:14px;line-height:20px;font-weight:500}.ui-navigation-item svg{width:16px;height:16px;flex:none}.ui-navigation-item>span{flex:1;min-width:0}.ui-navigation-item:hover{background:var(--surface-hover);color:var(--text-primary)}.ui-navigation-item.active{background:var(--surface-selected);color:var(--text-primary);font-weight:600}.ui-navigation-item small{color:var(--text-secondary);font-size:12px}.ui-navigation-item.is-disabled{color:var(--text-disabled)}@media(pointer:coarse){.ui-navigation-item{min-height:44px}}</style>
