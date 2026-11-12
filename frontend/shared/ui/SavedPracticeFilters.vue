<script setup lang="ts">
import { computed, ref } from 'vue'
import { useAccountPreferences } from '../preferences/store'
import type { FilterPreset } from '../preferences/schema'
import UiPopover from './UiPopover.vue'
const props=defineProps<{workspace:'drill'|'ei';query:Record<string,string>}>()
const emit=defineEmits<{apply:[query:Record<string,string>]}>()
const store=useAccountPreferences(),open=ref(false),anchor=ref<HTMLElement|null>(null),name=ref(''),error=ref('')
const key=computed(()=>`filters.${props.workspace}` as const),presets=computed(()=>store.values[key.value])
const allowed=new Set(['q','document','topic','source_category','type_group','exam_type','status','favorite','review_later','marker','include_structure','sort','collection','course','material','bucket','tier','kind','combined','state','scope'])
function save(){
 const title=name.value.trim();if(!title){error.value='请为筛选预设命名。';return}
 const existing=presets.value.find(item=>item.name===title)
 if(!existing&&presets.value.length>=10){error.value='最多保存10个预设，请先移除不用的预设。';return}
 const preset:FilterPreset={id:existing?.id||crypto.randomUUID(),name:title,query:Object.fromEntries(Object.entries(props.query).filter(([key,value])=>allowed.has(key)&&value))}
 store.set(key.value,existing?presets.value.map(item=>item.id===existing.id?preset:item):[...presets.value,preset]);name.value='';error.value=''
}
function apply(preset:FilterPreset){emit('apply',{...preset.query});open.value=false}
</script>
<template><button ref="anchor" type="button" class="ui-button ui-button--secondary" :aria-expanded="open" aria-haspopup="dialog" @click="open=!open">筛选预设<span v-if="presets.length"> · {{ presets.length }}</span></button><UiPopover v-model:open="open" :anchor="anchor" label="已保存筛选预设"><div class="saved-filter-panel"><h2>筛选预设</h2><p>显式保存到账号，在其他设备使用。分页和临时页面状态不保存。</p><p v-if="!presets.length">尚未保存预设。</p><ul><li v-for="preset in presets" :key="preset.id"><button type="button" class="preset-open" @click="apply(preset)">{{ preset.name }}</button><button type="button" class="ui-icon-button" :aria-label="`删除预设 ${preset.name}`" @click="store.set(key,presets.filter(item=>item.id!==preset.id))">×</button></li></ul><form @submit.prevent="save"><label>预设名称<input v-model="name" maxlength="80" placeholder="例如：导数 · 待复习" aria-label="筛选预设名称"/></label><button type="submit" class="ui-button ui-button--secondary" :disabled="!store.userId.value">保存当前筛选</button></form><small>同名预设会更新为当前筛选。</small><p v-if="error" role="alert">{{ error }}</p><p v-if="store.status.value==='offline'||store.status.value==='error'" role="status">保存待同步，可在设置中重试。</p></div></UiPopover></template>
<style scoped>.saved-filter-panel{width:304px;max-width:100%;padding:8px;min-width:0}.saved-filter-panel h2{font-size:16px;margin:0 0 8px}.saved-filter-panel p,.saved-filter-panel small{font-size:12px;line-height:1.6;color:var(--text-secondary)}ul{list-style:none;padding:0;margin:8px 0}li{display:flex;min-width:0;align-items:center;border-bottom:1px solid var(--border-subtle)}.preset-open{flex:1;min-width:0;text-align:left;border:0;background:transparent;color:var(--text-primary);padding:8px;font:inherit;overflow-wrap:anywhere;min-height:44px}.saved-filter-panel input{display:block;width:100%;min-width:0;min-height:44px;padding:8px;border:1px solid var(--border-control);border-radius:6px;color:var(--text-primary);background:var(--surface-page);font:inherit;margin:8px 0}.saved-filter-panel form{font-size:13px}.ui-icon-button,.ui-button{min-height:44px}.ui-icon-button{min-width:44px}</style>
