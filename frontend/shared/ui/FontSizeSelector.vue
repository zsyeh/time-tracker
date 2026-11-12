<script setup lang="ts">
import { computed } from 'vue'
import { useAccountPreferences } from '../preferences/store'
import { fontScales, type FontSize } from '../preferences/schema'
const store=useAccountPreferences()
const selected=computed({get:()=>store.values.font,set:(font:FontSize)=>store.set('font',font)})
const labels:Record<FontSize,string>={compact:'Compact · 90%',small:'Small · 95%（推荐）',default:'Default · 100%',large:'Large · 105%','extra-large':'Extra Large · 110%'}
</script>
<template><div class="font-size-setting"><label><span>全局字体大小</span><select v-model="selected" aria-label="全局字体大小"><option v-for="(_,id) in fontScales" :key="id" :value="id">{{ labels[id] }}</option></select></label><p class="font-size-preview">文字预览 · Study 892 · 12:34 <span aria-label="数学文本预览">x² + y²</span></p><small>即时预览并同步账号；题图尺寸与触控区域保持不变。</small><button v-if="selected!=='small'" type="button" class="ui-button ui-button--plain" @click="selected='small'">恢复推荐字号</button></div></template>
<style scoped>.font-size-setting{min-width:0;padding:12px 0}.font-size-setting label{display:flex;align-items:center;justify-content:space-between;gap:16px;min-height:44px}.font-size-setting select{max-width:65%;min-height:44px;border:0;background:var(--surface-subtle);color:var(--text-primary);font:inherit;padding:8px}.font-size-preview{font-size:var(--font-size-body);line-height:1.6;margin:12px 0 4px}.font-size-setting small{font-size:12px;color:var(--text-secondary);line-height:1.5}.font-size-setting button{min-height:44px}</style>
