<script setup lang="ts">
import {ref,computed,onBeforeUnmount,nextTick} from 'vue'
import type {Appearance} from '../appearance/palette'
import UiPopover from './UiPopover.vue'
const props=defineProps<{modelValue:Appearance}>();const emit=defineEmits<{'update:modelValue':[value:Appearance]}>()
const open=ref(false),trigger=ref<HTMLElement|null>(null),sheet=ref<HTMLDialogElement|null>(null),compact=ref(false)
const options:{value:Appearance;label:string}[]=[{value:'system',label:'跟随系统 · System'},{value:'light',label:'浅色 · Light'},{value:'dark',label:'深色 · Dark'}]
const valueLabel=computed(()=>options.find(item=>item.value===props.modelValue)?.label)
async function show(){compact.value=window.innerWidth<768;open.value=true;await nextTick();if(compact.value)sheet.value?.showModal()}
function close(){open.value=false;if(sheet.value?.open)sheet.value.close();trigger.value?.focus()}
function choose(value:Appearance){emit('update:modelValue',value);close()}
onBeforeUnmount(()=>{if(sheet.value?.open)sheet.value.close()})
</script>
<template><div class="appearance-selector"><button ref="trigger" type="button" class="ui-button ui-button--plain" aria-haspopup="dialog" :aria-expanded="open" @click="show">{{ valueLabel }}<span aria-hidden="true">⌄</span></button><UiPopover v-if="!compact" :open="open" :anchor="trigger" role="dialog" label="Appearance" @update:open="open=$event"><div role="radiogroup" aria-label="Appearance"><label v-for="item in options" :key="item.value" class="ui-selection-row"><input type="radio" name="appearance" :value="item.value" :checked="modelValue===item.value" @change="choose(item.value)"><span>{{ item.label }}</span></label></div></UiPopover><Teleport to="body"><dialog v-if="compact&&open" ref="sheet" class="ui-choice-sheet" aria-label="Appearance" @cancel="close" @close="open=false"><header><strong>外观 · Appearance</strong><button type="button" class="ui-icon-button" aria-label="关闭" @click="close">×</button></header><div role="radiogroup" aria-label="Appearance"><label v-for="item in options" :key="item.value" class="ui-selection-row"><input type="radio" name="appearance" :checked="modelValue===item.value" @change="choose(item.value)"><span>{{ item.label }}</span></label></div></dialog></Teleport></div></template>
