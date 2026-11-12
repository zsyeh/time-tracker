import { api, ApiError } from './api'
import { accountPreferences } from '../../../shared/preferences/store'
import { listContextKey, type ListContext, type PreviewAnchor, type PreviewItem, type PreviewPage } from './listContext'
export type { ListContext, PreviewAnchor, PreviewItem, PreviewPage } from './listContext'
export type PreviewLoadOptions={offset?:number;locate_entry?:string;locate_uuid?:string;fallback_index?:number;fresh?:boolean;signal?:AbortSignal}
const sessions=new Map<string,PreviewSession>()
let account=''
function owner(){return accountPreferences.userId.value||''}
function scope(){const next=owner();if(next!==account){for(const s of sessions.values())s.abort();sessions.clear();account=next}return next}
function abortError(){return new DOMException('Preview request cancelled','AbortError')}
function withSignal<T>(request:Promise<T>,signal?:AbortSignal):Promise<T>{
 if(!signal)return request
 if(signal.aborted)return Promise.reject(abortError())
 return new Promise((resolve,reject)=>{
  const cancel=()=>{signal.removeEventListener('abort',cancel);reject(abortError())}
  signal.addEventListener('abort',cancel,{once:true})
  request.then(value=>{signal.removeEventListener('abort',cancel);if(signal.aborted)reject(abortError());else resolve(value)},error=>{signal.removeEventListener('abort',cancel);reject(error)})
 })
}
function digest(value:string){let n=2166136261;for(let i=0;i<value.length;i++)n=Math.imul(n^value.charCodeAt(i),16777619);return(n>>>0).toString(36)}
function anchorKey(context:ListContext){return `learning.preview.anchor.v1.${scope()}.${context.workspace}.${digest(listContextKey(context))}`}
export function getPreviewAnchor(context:ListContext):PreviewAnchor|null{
 if(!scope())return null
 try{const data=JSON.parse(sessionStorage.getItem(anchorKey(context))||'null');const a=data?.anchor
  if(data?.context!==listContextKey(context)||!a||typeof a.entry_id!=='string'||typeof a.question_uuid!=='string'||!Number.isSafeInteger(a.index)||a.index<0||!Number.isFinite(a.offset)||Math.abs(a.offset)>1e7||typeof a.collection_version!=='string')return null
  return a
 }catch{return null}
}
export function savePreviewAnchor(context:ListContext,anchor:PreviewAnchor){if(!scope())return;try{sessionStorage.setItem(anchorKey(context),JSON.stringify({context:listContextKey(context),anchor,updatedAt:Date.now()}))}catch{}}
export class PreviewSession{
 readonly owner=owner()
 readonly context:ListContext
 count=0;version=''
 private pages=new Map<number,PreviewPage>()
 private inflight=new Map<string,Promise<PreviewPage>>()
 private controllers=new Set<AbortController>()
 private generation=0
 private refreshTask:Promise<PreviewPage>|null=null
 constructor(context:ListContext){this.context=context}
 get cachedCount(){if(this.owner!==owner())return 0;return [...this.pages.values()].reduce((sum,p)=>sum+p.results.length,0)}
 get(index:number):PreviewItem|undefined{if(this.owner!==owner())return;const p=this.pages.get(Math.floor(index/50)*50);return p?.results.find(x=>x.index===index)}
 find(entryId:string){if(this.owner!==owner())return undefined;for(const p of this.pages.values()){const item=p.results.find(x=>x.entry_id===entryId);if(item)return item}return undefined}
 abort(){for(const c of this.controllers)c.abort();this.controllers.clear();this.inflight.clear();this.refreshTask=null}
 invalidate(){this.generation++;this.abort();this.pages.clear();this.version='';this.count=0}
 async load(options:PreviewLoadOptions={}):Promise<PreviewPage>{
  if(!this.owner||scope()!==this.owner)throw abortError()
  if(options.signal?.aborted)throw abortError()
  if(!options.fresh&&this.refreshTask){await withSignal(this.refreshTask,options.signal);return this.load(options)}
  if(options.fresh){this.generation++;this.abort()}
  const offset=Math.floor(Math.max(0,options.offset||0)/50)*50
  const located=options.locate_entry?this.find(options.locate_entry):options.locate_uuid?[...this.pages.values()].flatMap(p=>p.results).find(x=>x.question_uuid===options.locate_uuid):undefined
  const batch=located?Math.floor(located.index/50)*50:offset
  const cached=this.pages.get(batch)
  if(!options.fresh&&cached&&(!options.locate_entry&&!options.locate_uuid||located)){
   this.pages.delete(batch);this.pages.set(batch,cached)
   if(!located)return cached
   const previous=this.get(located.index-1),next=this.get(located.index+1)
   if((located.index===0||previous)&&(located.index===this.count-1||next))return{...cached,located,previous_entry:previous||null,next_entry:next||null}
  }
  const key=JSON.stringify([this.generation,batch,options.locate_entry,options.locate_uuid,options.fallback_index,!!options.fresh])
  const pending=this.inflight.get(key);if(pending)return withSignal(pending,options.signal)
  const controller=new AbortController();this.controllers.add(controller)
  const cancel=()=>controller.abort();if(options.signal?.aborted)controller.abort();options.signal?.addEventListener('abort',cancel,{once:true})
  const generation=this.generation
  const params=new URLSearchParams({...this.context.query,source:this.context.source,offset:String(batch),limit:'50'})
  if(this.version&&!options.fresh)params.set('collection_version',this.version)
  if(options.locate_entry)params.set('locate_entry',options.locate_entry)
  if(options.locate_uuid)params.set('locate_uuid',options.locate_uuid)
  if(options.fallback_index!==undefined)params.set('fallback_index',String(Math.max(0,Math.floor(options.fallback_index))))
  let request!:Promise<PreviewPage>
  request=(async()=>{
   try{
    const data=await api<PreviewPage>(`/api/drill/collection-preview/?${params}`,{signal:controller.signal})
    if(generation!==this.generation||owner()!==this.owner||controller.signal.aborted)throw abortError()
    if(!Number.isSafeInteger(data.count)||data.count<0||!Array.isArray(data.results)||typeof data.collection_version!=='string')throw new Error('Invalid collection preview response')
    const pinned=params.get('collection_version')
    if(pinned&&data.collection_version!==pinned)throw new Error('Collection response version does not match the requested snapshot')
    if(this.version&&data.collection_version!==this.version)this.pages.clear()
    this.version=data.collection_version;this.count=data.count
    this.pages.delete(data.offset);this.pages.set(data.offset,data)
    while(this.pages.size>10)this.pages.delete(this.pages.keys().next().value!)
    return data
   }catch(error){
    if(error instanceof ApiError && (error.status===401 || (error.status===409 && typeof error.body.detail==='string' && error.body.detail.startsWith('Account changed.')))){this.invalidate();accountPreferences.reset();throw error}
    if(error instanceof ApiError&&error.status===409&&error.body.code==='COLLECTION_CHANGED'&&owner()===this.owner&&!options.signal?.aborted&&generation===this.generation){
     const anchor=getPreviewAnchor(this.context);this.invalidate()
     const refreshed=await this.load({locate_entry:options.locate_entry||anchor?.entry_id,locate_uuid:options.locate_uuid||anchor?.question_uuid,fallback_index:options.fallback_index??anchor?.index??offset,fresh:true,signal:options.signal})
     return {...refreshed,notice:refreshed.notice||'题单已更新，已恢复到附近题目。'}
    }
    throw error
   }finally{options.signal?.removeEventListener('abort',cancel);this.controllers.delete(controller);if(this.inflight.get(key)===request)this.inflight.delete(key);if(this.refreshTask===request)this.refreshTask=null}
  })()
  this.inflight.set(key,request);if(options.fresh)this.refreshTask=request;return request
 }
}
export function getPreviewSession(context:ListContext){const user=scope();if(!user)throw new Error('请先登录后预览题单。');const key=user+':'+listContextKey(context);let session=sessions.get(key);if(session){sessions.delete(key);sessions.set(key,session);return session}session=new PreviewSession(context);sessions.set(key,session);while(sessions.size>2){const first=sessions.keys().next().value!;sessions.get(first)?.abort();sessions.delete(first)}return session}
export function invalidatePreviewCollections(){for(const s of sessions.values())s.invalidate()}
if(typeof window!=='undefined')window.addEventListener('drill:question-state-changed',invalidatePreviewCollections)
