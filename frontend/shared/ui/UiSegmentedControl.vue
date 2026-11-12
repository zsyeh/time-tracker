<script setup lang="ts">

defineProps<{label:string;modelValue:string;options:{value:string;label:string}[]}>();const emit=defineEmits<{'update:modelValue':[value:string]}>()
function navigate(event:KeyboardEvent,options:{value:string}[],current:string){const key=event.key;if(!['ArrowLeft','ArrowRight','Home','End'].includes(key))return;event.preventDefault();let i=options.findIndex(x=>x.value===current);i=key==='Home'?0:key==='End'?options.length-1:(i+(key==='ArrowRight'?1:-1)+options.length)%options.length;emit('update:modelValue',options[i].value);(event.currentTarget as HTMLElement).querySelectorAll<HTMLInputElement>('input')[i]?.focus()}

</script>
<template><div class="ui-segmented" role="radiogroup" :aria-label="label" @keydown="navigate($event,options,modelValue)"><label v-for="item in options" :key="item.value" :class="{selected:item.value===modelValue}"><input type="radio" :name="label" :checked="item.value===modelValue" :tabindex="item.value===modelValue?0:-1" @change="$emit('update:modelValue',item.value)">{{ item.label }}</label></div></template>
<style scoped>.ui-segmented{display:inline-flex;gap:4px;padding:4px;background:var(--surface-subtle);border-radius:8px}.ui-segmented label{display:flex;align-items:center;min-height:var(--control-height);padding:4px 12px;border-radius:6px;cursor:pointer}.ui-segmented label.selected{background:var(--surface-selected);font-weight:600}.ui-segmented input{position:absolute;opacity:0;width:1px;height:1px}.ui-segmented label:has(:focus-visible){outline:2px solid var(--accent-focus)}</style>
