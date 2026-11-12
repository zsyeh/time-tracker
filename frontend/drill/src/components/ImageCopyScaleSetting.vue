<script setup lang="ts">
import { ref, watch } from 'vue'
import { validPreference } from '../../../shared/preferences/schema'
import { uiText } from '../lib/uiText'
const props=defineProps<{modelValue:number}>()
const emit=defineEmits<{ 'update:modelValue':[value:number] }>()
const presets=[1,2,3,4]
const mode=ref(presets.includes(props.modelValue)?String(props.modelValue):'custom')
const draft=ref(String(props.modelValue)),error=ref('')
watch(()=>props.modelValue,value=>{mode.value=presets.includes(value)?String(value):'custom';draft.value=String(value);error.value=''})
function select(event:Event){
 mode.value=(event.target as HTMLSelectElement).value;error.value=''
 if(mode.value!=='custom')emit('update:modelValue',Number(mode.value))
 else draft.value=String(props.modelValue)
}
function save(){
 const value=Number(draft.value)
 if(!validPreference('practice.image_copy_scale',value)){error.value=uiText('请输入 1 到 8 之间的倍率。');return}
 error.value='';emit('update:modelValue',value)
}
</script>
<template>
 <div class="settings-row image-copy-scale-setting">
  <span><strong>{{ uiText('复制倍率') }}</strong><small>{{ uiText('倍率会保存到账号。适用于手动和翻题复制；只放大像素，不增加原图细节。超大图片会限制输出尺寸。') }}</small></span>
  <div class="scale-controls">
   <select :value="mode" :aria-label="uiText('复制倍率')" @change="select"><option v-for="scale in presets" :key="scale" :value="String(scale)">{{ scale }}×</option><option value="custom">{{ uiText('自定义') }}</option></select>
   <form v-if="mode==='custom'" novalidate @submit.prevent="save"><input v-model="draft" type="number" min="1" max="8" step="any" inputmode="decimal" :aria-label="uiText('自定义复制倍率')" :aria-invalid="!!error"/><span aria-hidden="true">×</span><button type="submit" class="ui-button ui-button--secondary">{{ uiText('保存倍率') }}</button></form>
   <p v-if="error" role="alert">{{ error }}</p>
  </div>
 </div>
</template>
<style scoped>
.image-copy-scale-setting{display:flex;flex-wrap:wrap;gap:16px;align-items:center;padding:12px 0;min-height:56px;border-top:1px solid var(--border-subtle)}
.image-copy-scale-setting>span{flex:1 1 240px;min-width:0}strong{font-size:14px;font-weight:500}small{display:block;margin-top:4px;font-size:12px;line-height:1.5;color:var(--text-secondary)}
.scale-controls{display:flex;flex-wrap:wrap;justify-content:flex-end;align-items:center;gap:8px;max-width:100%;min-width:0}select,input,button{min-height:44px;font:inherit}select{max-width:100%;background:transparent;color:var(--text-primary);border:0;padding:8px}form{display:flex;flex-wrap:wrap;align-items:center;gap:8px;max-width:100%}input{width:80px;max-width:100%;box-sizing:border-box}p{width:100%;font-size:12px;color:var(--status-danger)}
</style>
