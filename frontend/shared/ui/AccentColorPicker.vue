<script setup lang="ts">
import {ref,nextTick,onBeforeUnmount} from 'vue'
import {accents,accentIds,type Accent} from '../appearance/palette'
import UiPopover from './UiPopover.vue'
defineProps<{modelValue:Accent}>();const emit=defineEmits<{'update:modelValue':[value:Accent]}>()
const open=ref(false),compact=ref(false),trigger=ref<HTMLElement|null>(null),sheet=ref<HTMLDialogElement|null>(null)
async function show(){compact.value=window.innerWidth<768;open.value=true;await nextTick();if(compact.value)sheet.value?.showModal()}
function close(){open.value=false;if(sheet.value?.open)sheet.value.close();trigger.value?.focus()}
function choose(value:Accent){emit('update:modelValue',value);close()}
onBeforeUnmount(()=>{if(sheet.value?.open)sheet.value.close()})
</script>
<template><div><button ref="trigger" type="button" class="ui-button ui-button--plain" aria-haspopup="dialog" :aria-expanded="open" @click="show"><span class="accent-swatch" :style="{background:accents[modelValue].light.solid}" aria-hidden="true"/>{{ accents[modelValue].label }}<span aria-hidden="true">⌄</span></button><UiPopover v-if="!compact" :open="open" :anchor="trigger" :width="360" role="dialog" label="Accent color" @update:open="open=$event"><div class="accent-picker" role="radiogroup" aria-label="Accent color"><label v-for="id in accentIds" :key="id" class="ui-selection-row"><input type="radio" name="accent-color" :checked="modelValue===id" @change="choose(id)"><span class="accent-swatch" :style="{background:accents[id].light.solid}" aria-hidden="true"/><span>{{ accents[id].label }}</span></label></div></UiPopover><Teleport to="body"><dialog v-if="compact&&open" ref="sheet" class="ui-choice-sheet" aria-label="Accent color" @cancel="close" @close="open=false"><header><strong>强调色 · Accent color</strong><button type="button" class="ui-icon-button" aria-label="关闭" @click="close">×</button></header><div class="accent-picker" role="radiogroup" aria-label="Accent color"><label v-for="id in accentIds" :key="id" class="ui-selection-row"><input type="radio" name="accent-color" :checked="modelValue===id" @change="choose(id)"><span class="accent-swatch" :style="{background:accents[id].light.solid}" aria-hidden="true"/><span>{{ accents[id].label }}</span></label></div></dialog></Teleport></div></template>
<style scoped>.accent-picker{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:4px}.accent-swatch{width:16px;height:16px;border-radius:50%;box-shadow:inset 0 0 0 1px rgb(0 0 0/.15);flex:none}</style>
