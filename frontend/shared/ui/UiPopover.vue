<script setup lang="ts">

import { computed,nextTick,onBeforeUnmount,ref,watch } from 'vue'
const props=withDefaults(defineProps<{open:boolean;anchor:HTMLElement|null|{x:number;y:number};placement?:'bottom-start'|'bottom-end';width?:number;label?:string;role?:'dialog'|'none';id?:string}>(),{width:272,placement:'bottom-start',role:'none'})
const emit=defineEmits<{'update:open':[value:boolean];close:[reason:string]}>()
const panel=ref<HTMLElement|null>(null),style=ref<Record<string,string>>({}),host=ref<HTMLElement|string>('body')
let observer:ResizeObserver|undefined
let frame=0
function close(reason:string){emit('update:open',false);emit('close',reason);if(reason==='escape' && props.anchor instanceof HTMLElement)props.anchor.focus()}
function position(){
 if(!props.open||!props.anchor)return
 const v=window.visualViewport,x=v?.offsetLeft||0,y=v?.offsetTop||0,w=v?.width||window.innerWidth,h=v?.height||window.innerHeight
 const rect=props.anchor instanceof HTMLElement?props.anchor.getBoundingClientRect():{left:props.anchor.x,right:props.anchor.x,top:props.anchor.y,bottom:props.anchor.y}
 const width=Math.min(props.width,w-16),height=Math.min(panel.value?.scrollHeight||300,520,h-16)
 const left=Math.max(x+8,Math.min(props.placement==='bottom-end'?rect.right-width:rect.left,x+w-width-8))
 const top=Math.max(y+8,Math.min(rect.bottom+8+height<=y+h-8?rect.bottom+8:rect.top-height-8,y+h-height-8))
 style.value={left:`${left}px`,top:`${top}px`,width:`${width}px`,maxHeight:`${Math.max(80,Math.min(520,y+h-top-8))}px`}
}
function schedule(){if(window.cancelAnimationFrame)window.cancelAnimationFrame(frame);else clearTimeout(frame);frame=window.requestAnimationFrame?window.requestAnimationFrame(position):window.setTimeout(position,0)}
function outside(event:Event){const node=event.target;if(node instanceof Node&&(panel.value?.contains(node)||(props.anchor instanceof HTMLElement&&props.anchor.contains(node))))return;close('outside')}
function key(event:KeyboardEvent){if(event.key==='Escape'){event.preventDefault();event.stopPropagation();close('escape')}}
function cleanup(){document.removeEventListener('pointerdown',outside);document.removeEventListener('keydown',key);window.removeEventListener('resize',schedule);window.removeEventListener('scroll',schedule,true);window.visualViewport?.removeEventListener('resize',schedule);window.visualViewport?.removeEventListener('scroll',schedule);observer?.disconnect();if(window.cancelAnimationFrame)window.cancelAnimationFrame(frame);else clearTimeout(frame)}
watch(()=>props.open,async open=>{cleanup();if(!open)return;const dialog=props.anchor instanceof HTMLElement?props.anchor.closest('dialog'):null;host.value=dialog?.querySelector<HTMLElement>('[data-overlay-host]')||dialog||'body';await nextTick();position();document.addEventListener('pointerdown',outside);document.addEventListener('keydown',key);window.addEventListener('resize',schedule);window.addEventListener('scroll',schedule,true);window.visualViewport?.addEventListener('resize',schedule);window.visualViewport?.addEventListener('scroll',schedule);if(typeof ResizeObserver!=='undefined'){observer=new ResizeObserver(schedule);if(props.anchor instanceof HTMLElement)observer.observe(props.anchor);if(panel.value)observer.observe(panel.value)};(panel.value?.querySelector<HTMLElement>('input:checked,[aria-checked="true"],a.active')||panel.value?.querySelector<HTMLElement>('button:not(:disabled),a,input,select'))?.focus()},{immediate:true})
watch(()=>props.anchor,(anchor,previous)=>{if(props.open&&anchor!==previous)close('anchor-change')})
onBeforeUnmount(cleanup)
const semanticRole=computed(()=>props.role==='none'?undefined:props.role)

</script>
<template><Teleport :to="host"><div v-if="open" :id="id" ref="panel" class="ui-popover" data-ui-popover :style="style" :role="semanticRole" :aria-label="label"><slot/></div></Teleport></template>
