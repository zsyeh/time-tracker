// @vitest-environment jsdom
import { createApp, nextTick } from 'vue'
import { expect, it } from 'vitest'
import ImageCopyScaleSetting from './ImageCopyScaleSetting.vue'
it('offers four quick presets and validates an explicitly saved custom multiplier',async()=>{
 const host=document.createElement('div'),values:number[]=[]
 const app=createApp(ImageCopyScaleSetting,{modelValue:1,'onUpdate:modelValue':(v:number)=>values.push(v)});app.mount(host)
 try{
  const select=host.querySelector('select')!;select.value='4';select.dispatchEvent(new Event('change'));await nextTick();expect(values).toEqual([4])
  select.value='custom';select.dispatchEvent(new Event('change'));await nextTick()
  const input=host.querySelector('input')!,form=host.querySelector('form')!
  input.value='3.5';input.dispatchEvent(new Event('input'));form.dispatchEvent(new Event('submit'));await nextTick();expect(values).toEqual([4,3.5])
  input.value='9';input.dispatchEvent(new Event('input'));form.dispatchEvent(new Event('submit'));await nextTick();expect(values).toEqual([4,3.5]);expect(host.querySelector('[role=alert]')).not.toBeNull()
 }finally{app.unmount()}
})
