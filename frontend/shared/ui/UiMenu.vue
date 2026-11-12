<script setup lang="ts">

import {ref} from 'vue'
import UiPopover from './UiPopover.vue'
export interface MenuItem{id:string;label:string;disabled?:boolean;checked?:boolean;tone?:'danger';run:()=>void}
defineProps<{open:boolean;anchor:HTMLElement|null;items:MenuItem[];label?:string}>();const emit=defineEmits<{'update:open':[value:boolean]}>()
const menu=ref<HTMLElement|null>(null);let typed='',typing=0
function key(event:KeyboardEvent){const buttons=Array.from(menu.value?.querySelectorAll<HTMLButtonElement>('button:not(:disabled)')||[]);const at=buttons.indexOf(document.activeElement as HTMLButtonElement);let index=-1;if(event.key==='ArrowDown')index=(at+1)%buttons.length;else if(event.key==='ArrowUp')index=(at-1+buttons.length)%buttons.length;else if(event.key==='Home')index=0;else if(event.key==='End')index=buttons.length-1;else if(event.key==='Tab'){emit('update:open',false);return}else if(event.key.length===1&&!event.ctrlKey&&!event.metaKey){clearTimeout(typing);typed+=event.key.toLocaleLowerCase();typing=window.setTimeout(()=>typed='',500);index=buttons.findIndex(b=>b.textContent?.trim().toLocaleLowerCase().startsWith(typed))}if(index>=0&&buttons[index]){event.preventDefault();buttons[index].focus()}}
function activate(item:MenuItem){if(item.disabled)return;emit('update:open',false);item.run()}

</script>
<template><UiPopover :open="open" :anchor="anchor" :label="label" @update:open="$emit('update:open',$event)"><div ref="menu" class="ui-menu" role="menu" :aria-label="label" @keydown="key"><button v-for="item in items" :key="item.id" type="button" :role="item.checked===undefined?'menuitem':'menuitemcheckbox'" :aria-checked="item.checked" :disabled="item.disabled" :data-tone="item.tone" @click="activate(item)">{{ item.label }}<span v-if="item.checked" aria-hidden="true"> ✓</span></button></div></UiPopover></template>
