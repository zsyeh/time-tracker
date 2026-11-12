/** Preview-only media. Never warms answers, writes learning state or keeps an unbounded visited cache. */
export type PreviewImageAsset = { url: string; width: number; height: number }
export type PreviewImageState = { status: 'waiting'|'loading'|'ready'|'error'; url?: string; error?: string }
export type PreviewImageHandle = { release(): void; priority(value: number): void; retry(): void }
type Subscriber = { priority: number; notify(state: PreviewImageState): void }
type Entry = { asset: PreviewImageAsset; subscribers: Map<symbol,Subscriber>; phase: 'waiting'|'fetching'|'decoding'|'ready'|'error'; controller?: AbortController; objectUrl?: string; image?: HTMLImageElement; blob?: Blob; error?: string; serial: number }
export type PreviewImageStats = { entries: number; fetching: number; decoding: number; resident: number; pixels: number; overBudget: boolean }
export type PreviewImagePipeline = ReturnType<typeof createPreviewImagePipeline>

export function createPreviewImagePipeline(options: { fetch?: typeof fetch; userId?: string; maxFetch?: number; maxDecode?: number; maxResident?: number; maxPixels?: number } = {}) {
 const fetcher=options.fetch ?? fetch, maxFetch=options.maxFetch ?? 4, maxDecode=options.maxDecode ?? 2
 const maxResident=options.maxResident ?? 12, maxPixels=options.maxPixels ?? 32*1024*1024
 const entries=new Map<string,Entry>();let fetching=0,decoding=0,serial=0,disposed=false
 const priority=(entry:Entry)=>Math.min(...[...entry.subscribers.values()].map(s=>s.priority),Infinity)
 const pixels=(entry:Entry)=>Math.max(1,entry.asset.width||1024)*Math.max(1,entry.asset.height||768)
 const active=()=>[...entries.values()].filter(e=>['fetching','decoding','ready'].includes(e.phase))
 function notify(entry:Entry){const state:PreviewImageState={status:entry.phase==='ready'?'ready':entry.phase==='error'?'error':entry.phase==='waiting'?'waiting':'loading',...(entry.objectUrl&&entry.phase==='ready'?{url:entry.objectUrl}:{}),...(entry.error?{error:entry.error}:{})};for(const s of entry.subscribers.values())s.notify(state)}
 function clearMedia(entry:Entry){if(entry.image){entry.image.src='';entry.image=undefined}if(entry.objectUrl){URL.revokeObjectURL(entry.objectUrl);entry.objectUrl=undefined}entry.blob=undefined}
 function evict(entry:Entry){entry.serial=++serial;entry.controller?.abort();entry.controller=undefined;clearMedia(entry);entry.phase='waiting';entry.error=undefined;notify(entry)}
 function admit(entry:Entry){
  let held=active();let total=held.reduce((sum,e)=>sum+pixels(e),0)
  while(held.length>=maxResident||total+pixels(entry)>maxPixels){
   const victim=held.filter(e=>e.phase==='ready'&&priority(e)>priority(entry)).sort((a,b)=>priority(b)-priority(a)||a.serial-b.serial)[0]
   if(!victim) return priority(entry)===0 // Visible scans may exceed the SOFT budget; never silently crop/drop them.
   evict(victim);held=active();total=held.reduce((sum,e)=>sum+pixels(e),0)
  }
  return true
 }
 function fail(entry:Entry, token:number, error:unknown){if(entry.serial!==token||disposed)return;clearMedia(entry);entry.phase='error';entry.error=error instanceof Error?error.message:'题图加载失败';notify(entry)}
 function decode(entry:Entry){
  const token=entry.serial;decoding++;entry.phase='decoding';notify(entry)
  const image=new Image();entry.image=image;image.decoding='async';image.referrerPolicy='same-origin'
  const timeout=window.setTimeout(()=>entry.controller?.abort(),20000)
  const cancelled=new Promise<never>((_resolve,reject)=>{entry.controller?.signal.addEventListener('abort',()=>reject(new DOMException('Image cancelled','AbortError')),{once:true})})
  image.src=entry.objectUrl!
  Promise.race([image.decode(),cancelled]).then(()=>{
   if(entry.serial!==token||disposed)return
   entry.asset={...entry.asset,width:image.naturalWidth||entry.asset.width,height:image.naturalHeight||entry.asset.height}
   entry.phase='ready';entry.blob=undefined;notify(entry)
  }).catch(error=>fail(entry,token,error)).finally(()=>{window.clearTimeout(timeout);decoding--;drain()})
 }
 function begin(entry:Entry){
  fetching++;entry.phase='fetching';entry.serial=++serial;const token=entry.serial
  entry.controller=new AbortController();const controller=entry.controller;notify(entry)
  const timeout=window.setTimeout(()=>controller.abort(),20000)
  const headers:Record<string,string>={};if(options.userId)headers['X-Learning-User-ID']=options.userId
  fetcher(entry.asset.url,{credentials:'same-origin',signal:controller.signal,headers}).then(async response=>{
   if(!response.ok)throw new Error(`题图读取失败（HTTP ${response.status}）`)
   const blob=await response.blob();if(entry.serial!==token||disposed)return
   entry.blob=blob;entry.objectUrl=URL.createObjectURL(blob)
   // Fetched blobs wait behind the separate decode admission limit.
  }).catch(error=>fail(entry,token,error)).finally(()=>{window.clearTimeout(timeout);fetching--;drain()})
 }
 function drain(){
  if(disposed)return
  const fetched=[...entries.values()].filter(e=>e.phase==='fetching'&&e.blob).sort((a,b)=>priority(a)-priority(b))
  for(const entry of fetched){if(decoding>=maxDecode)break;decode(entry)}
  const waiting=[...entries.values()].filter(e=>e.phase==='waiting'&&e.subscribers.size).sort((a,b)=>priority(a)-priority(b)||a.serial-b.serial)
  // A fast scrollbar jump must not queue the visible scan behind distant prefetches.
  if(fetching>=maxFetch&&waiting.some(e=>priority(e)===0)){
   const victim=[...entries.values()].filter(e=>e.phase==='fetching'&&!e.blob&&priority(e)>0&&!e.controller?.signal.aborted).sort((a,b)=>priority(b)-priority(a))[0]
   if(victim)evict(victim)
  }
  for(const entry of waiting){if(fetching>=maxFetch)break;if(admit(entry))begin(entry)}
 }
 function request(asset:PreviewImageAsset, listener:(state:PreviewImageState)=>void, initialPriority=2):PreviewImageHandle{
  if(disposed){listener({status:'error',error:'预览已关闭'});return{release(){},priority(){},retry(){}}}
  let entry=entries.get(asset.url)
  if(!entry){entry={asset:{...asset},subscribers:new Map(),phase:'waiting',serial:++serial};entries.set(asset.url,entry)}
  const item=entry, key=Symbol();item.subscribers.set(key,{priority:initialPriority,notify:listener});notify(item);drain()
  return {release(){item.subscribers.delete(key);if(!item.subscribers.size){evict(item);entries.delete(asset.url)}drain()},priority(value){const subscriber=item.subscribers.get(key);if(subscriber){subscriber.priority=value;drain()}},retry(){if(item.phase==='error'){item.phase='waiting';item.error=undefined;notify(item);drain()}}}
 }
 function stats():PreviewImageStats{const held=active();const total=held.reduce((sum,e)=>sum+pixels(e),0);return{entries:entries.size,fetching,decoding,resident:held.length,pixels:total,overBudget:held.length>maxResident||total>maxPixels}}
 function dispose(){disposed=true;for(const e of entries.values())evict(e);entries.clear()}
 return {request,stats,dispose}
}
