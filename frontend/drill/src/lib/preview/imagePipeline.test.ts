// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPreviewImagePipeline, type PreviewImageState } from './imagePipeline'
const tick = async () => { for (let i=0;i<8;i++) await Promise.resolve() }
let decoded: Array<() => void>, fetches: Array<{resolve:(value:Response)=>void; signal:AbortSignal}>, revoked:string[]
class FakeImage {
 src='';decoding='';referrerPolicy='';naturalWidth=100;naturalHeight=100
 decode(){return new Promise<void>(resolve=>decoded.push(resolve))}
}
const asset = (n:number,width=100,height=100)=>({url:`/asset/${n}`,width,height})
const response = () => ({ok:true,status:200,blob:async()=>new Blob(['png'])}) as Response
const fakeFetch = vi.fn((_url:RequestInfo|URL, init?:RequestInit)=>new Promise<Response>((resolve,reject)=>{
 const signal=init!.signal as AbortSignal;fetches.push({resolve,signal});signal.addEventListener('abort',()=>reject(new DOMException('abort','AbortError')))
}))
beforeEach(()=>{decoded=[];fetches=[];revoked=[];fakeFetch.mockClear();vi.stubGlobal('Image',FakeImage);let serial=0;URL.createObjectURL=vi.fn(()=>`blob:${++serial}`);URL.revokeObjectURL=vi.fn(url=>revoked.push(url))})
afterEach(()=>vi.unstubAllGlobals())
describe('preview-only media admission',()=>{
 it('bounds concurrent transfer and decode independently, releases every object URL',async()=>{
  const p=createPreviewImagePipeline({fetch:fakeFetch as typeof fetch})
  const handles=Array.from({length:20},(_,i)=>p.request(asset(i),()=>{},2))
  expect(fetches).toHaveLength(4);expect(p.stats().fetching).toBe(4)
  fetches.slice().forEach(f=>f.resolve(response()));await tick()
  expect(p.stats().decoding).toBe(2);expect(p.stats().fetching).toBeLessThanOrEqual(4)
  expect(p.stats().resident).toBeLessThanOrEqual(12)
  decoded.splice(0).forEach(resolve=>resolve());await tick()
  expect(p.stats().decoding).toBeLessThanOrEqual(2)
  handles.forEach(h=>h.release());await tick()
  expect(p.stats().entries).toBe(0);expect(revoked.length).toBeGreaterThan(0);p.dispose()
 })
 it('deduplicates visible leases and sends account affinity only to the image request',async()=>{
  const p=createPreviewImagePipeline({fetch:fakeFetch as typeof fetch,userId:'42'})
  const states:PreviewImageState[]=[]
  const a=p.request(asset(1),s=>states.push(s),0),b=p.request(asset(1),()=>{},0)
  expect(fakeFetch).toHaveBeenCalledTimes(1)
  expect(fakeFetch.mock.calls[0]?.[1]?.headers).toEqual({'X-Learning-User-ID':'42'})
  fetches[0]!.resolve(response());await tick();decoded[0]!();await tick()
  expect(states.at(-1)?.status).toBe('ready');expect(p.stats().resident).toBe(1)
  a.release();expect(p.stats().entries).toBe(1);b.release();expect(p.stats().entries).toBe(0);expect(revoked).toHaveLength(1);p.dispose()
 })
 it('allows a genuine visible oversize exception and does not keep visited assets',async()=>{
  const p=createPreviewImagePipeline({fetch:fakeFetch as typeof fetch,maxPixels:100})
  const background=p.request(asset(1),()=>{},2);expect(fetches).toHaveLength(0)
  const visible=p.request(asset(2),()=>{},0);expect(fetches).toHaveLength(1);expect(p.stats().overBudget).toBe(true)
  background.release();visible.release();await tick();expect(fetches[0]?.signal.aborted).toBe(true);expect(p.stats().entries).toBe(0);p.dispose()
 })
 it('does not let a late response revive a released row',async()=>{
  const p=createPreviewImagePipeline({fetch:fakeFetch as typeof fetch});const states:PreviewImageState[]=[]
  const h=p.request(asset(1),s=>states.push(s),0);h.release();fetches[0]!.resolve(response());await tick()
  expect(p.stats().entries).toBe(0);expect(states.some(s=>s.status==='ready')).toBe(false);expect(URL.createObjectURL).not.toHaveBeenCalled();p.dispose()
 })
 it('keeps a retry on the same lease after a transfer failure',async()=>{
  const p=createPreviewImagePipeline({fetch:fakeFetch as typeof fetch});const states:PreviewImageState[]=[]
  const h=p.request(asset(1),s=>states.push(s),0);fetches[0]!.resolve({ok:false,status:503} as Response);await tick()
  expect(states.at(-1)?.status).toBe('error');h.retry();expect(fetches).toHaveLength(2);h.release();await tick();p.dispose()
 })
})

it('lets a newly visible scan preempt a distant prefetch after a scrollbar jump',async()=>{
 const p=createPreviewImagePipeline({fetch:fakeFetch as typeof fetch,maxFetch:2})
 const a=p.request(asset(1),()=>{},2),b=p.request(asset(2),()=>{},2)
 const visible=p.request(asset(99),()=>{},0)
 expect(fetches.some(f=>f.signal.aborted)).toBe(true)
 await tick()
 expect(fakeFetch.mock.calls.at(-1)?.[0]).toBe('/asset/99')
 expect(p.stats().fetching).toBeLessThanOrEqual(2)
 a.release();b.release();visible.release();await tick();p.dispose()
})
