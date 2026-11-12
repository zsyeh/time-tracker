// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import PreviewAssetImage from './PreviewAssetImage.vue'
import type { PreviewImagePipeline } from '../../lib/preview/imagePipeline'
const observers: Array<{ callback:IntersectionObserverCallback }> = []
let app:App|undefined,host:HTMLDivElement
beforeEach(()=>{
 observers.length=0;host=document.createElement('div');document.body.append(host)
 vi.stubGlobal('IntersectionObserver',class{constructor(callback:IntersectionObserverCallback){observers.push({callback})}observe(){}disconnect(){}})
})
afterEach(()=>{app?.unmount();host.remove();vi.unstubAllGlobals()})
async function mount(){
 const open=vi.fn(),zoom=vi.fn(),release=vi.fn(),priority=vi.fn()
 const pipeline={request:vi.fn((_asset,notify)=>{notify({status:'ready',url:'blob:fixture'});return{release,priority,retry:vi.fn()}})} as unknown as PreviewImagePipeline
 app=createApp(PreviewAssetImage,{asset:{id:1,url:'/asset/1',width:1000,height:500},pipeline,scroller:host,label:'题1',onOpen:open,onZoom:zoom});app.mount(host)
 observers[0]!.callback([{isIntersecting:true}] as IntersectionObserverEntry[],{} as IntersectionObserver);await nextTick()
 return {open,zoom,release,priority,button:host.querySelector<HTMLButtonElement>('.preview-image-open')!}
}
function pointer(element:Element,type:string,id:number,x=0,primary=true){const event=new Event(type,{bubbles:true});Object.assign(event,{pointerId:id,clientX:x,clientY:0,isPrimary:primary});element.dispatchEvent(event)}
it('opens the original question on one image tap without placing controls over its content',async()=>{
 const {open,button}=await mount();pointer(button,'pointerdown',1);pointer(button,'pointerup',1);button.click()
 expect(open).toHaveBeenCalledTimes(1);expect(host.querySelector('.preview-zoom')).toBeNull()
})
it('does not turn pinch, drag or browser pointer cancellation into question navigation',async()=>{
 const {open,button}=await mount()
 pointer(button,'pointerdown',1);pointer(button,'pointerdown',2,0,false);pointer(button,'pointerup',2);pointer(button,'pointerup',1);button.click();expect(open).not.toHaveBeenCalled()
 pointer(button,'pointerdown',1);pointer(button,'pointermove',1,20);pointer(button,'pointerup',1);button.click();expect(open).not.toHaveBeenCalled()
 pointer(button,'pointerdown',1);pointer(button,'pointercancel',1);button.click();expect(open).not.toHaveBeenCalled()
 pointer(button,'pointerdown',1);pointer(button,'pointerup',1);button.click();expect(open).toHaveBeenCalledTimes(1)
})
it('releases scans leaving the near viewport rather than accumulating visited decoded images',async()=>{
 const {release}=await mount();observers[0]!.callback([{isIntersecting:false}] as IntersectionObserverEntry[],{} as IntersectionObserver);await nextTick()
 expect(release).toHaveBeenCalledTimes(1);expect(host.querySelector('img')).toBeNull()
})
