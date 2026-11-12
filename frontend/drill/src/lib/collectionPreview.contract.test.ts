// @vitest-environment jsdom
import { beforeEach, expect, it, vi } from 'vitest'
import { api, ApiError } from './api'
import { accountPreferences } from '../../../shared/preferences/store'
import { buildListContext, type PreviewItem, type PreviewPage } from './listContext'
import { getPreviewAnchor, getPreviewSession, savePreviewAnchor } from './collectionPreview'
vi.mock('./runtimePath',()=>({runtimeWorkspace:'drill'}))
vi.mock('./api',()=>({api:vi.fn(),ApiError:class extends Error{constructor(public status:number,message:string,public body:Record<string,unknown>={}){super(message)}}}))
vi.mock('../../../shared/preferences/store',async()=>{const {ref}=await import('vue');return{accountPreferences:{userId:ref<string|null>(''),reset:vi.fn()}}})
let id=0
beforeEach(()=>{vi.clearAllMocks();sessionStorage.clear();accountPreferences.userId.value='preview-test-'+(++id);vi.mocked(accountPreferences.reset).mockImplementation(()=>{accountPreferences.userId.value=null})})
const context=()=>buildListContext('attempts',{q:'导数'},'/insight?questions_page=2')
function item(index:number):PreviewItem{return{entry_id:'attempt:'+(index+1),question_uuid:index<2?'same-question':'question-'+index,index,label:'Synthetic '+index,document:'Book',topic:'Topic',state:'unattempted',preview:{question_markdown:'Synthetic prompt',assets:[]}}}
function page(offset=0,version='v1',count=1000,locatedIndex?:number):PreviewPage{return{count,offset,limit:50,has_more:offset+50<count,collection_version:version,located:locatedIndex===undefined?null:item(locatedIndex),results:Array.from({length:Math.max(0,Math.min(50,count-offset))},(_,i)=>item(offset+i)),previous_entry:locatedIndex!==undefined&&locatedIndex>0?item(locatedIndex-1):null,next_entry:locatedIndex!==undefined&&locatedIndex+1<count?item(locatedIndex+1):null}}
function deferred<T>(){let resolve!:(value:T)=>void,reject!:(reason:unknown)=>void;const promise=new Promise<T>((a,b)=>{resolve=a;reject=b});return{promise,resolve,reject}}
it('loads a 1000-entry list in pages and bounds its LRU cache to 500 entries',async()=>{
 vi.mocked(api).mockImplementation(async(url)=>page(Number(new URL(String(url),'http://fixture').searchParams.get('offset'))) as never)
 const session=getPreviewSession(context());await session.load()
 expect(session.count).toBe(1000);expect(session.cachedCount).toBe(50);expect(session.get(600)).toBeUndefined();expect(api).toHaveBeenCalledTimes(1)
 for(let offset=50;offset<1000;offset+=50)await session.load({offset})
 expect(session.cachedCount).toBe(500);expect(session.get(0)).toBeUndefined();expect(session.get(999)?.index).toBe(999)
 await session.load({offset:0});expect(session.cachedCount).toBe(500);expect(session.get(0)?.index).toBe(0)
 expect(session.get(500)).toBeUndefined()
})
it('shares an inflight request and locates duplicate UUID entries by attempt identity',async()=>{
 const pending=deferred<PreviewPage>();vi.mocked(api).mockReturnValueOnce(pending.promise)
 const session=getPreviewSession(context()),a=session.load(),b=session.load()
 expect(api).toHaveBeenCalledTimes(1);pending.resolve(page());await Promise.all([a,b])
 const located=await session.load({locate_entry:'attempt:2'})
 expect(located.located).toMatchObject({entry_id:'attempt:2',question_uuid:'same-question',index:1})
 expect(located.previous_entry?.entry_id).toBe('attempt:1');expect(located.next_entry?.entry_id).toBe('attempt:3')
 expect(api).toHaveBeenCalledTimes(1)
})
it('rejects a canceled caller and does not accept an ignored-abort network response into its cache',async()=>{
 const pending=deferred<PreviewPage>();vi.mocked(api).mockReturnValueOnce(pending.promise)
 const controller=new AbortController(),session=getPreviewSession(context()),request=session.load({signal:controller.signal})
 const rejected=expect(request).rejects.toMatchObject({name:'AbortError'})
 controller.abort();pending.resolve(page());await rejected
 expect(session.cachedCount).toBe(0);expect(session.count).toBe(0)
})
it('prevents an older request from overwriting a later fresh snapshot even when transport ignores AbortSignal',async()=>{
 const old=deferred<PreviewPage>(),fresh=deferred<PreviewPage>();vi.mocked(api).mockReturnValueOnce(old.promise).mockReturnValueOnce(fresh.promise)
 const session=getPreviewSession(context()),a=session.load(),rejected=expect(a).rejects.toMatchObject({name:'AbortError'}),b=session.load({fresh:true})
 fresh.resolve(page(0,'v2',999));await b;old.resolve(page(0,'v1',1000));await rejected
 expect(session.version).toBe('v2');expect(session.count).toBe(999)
})
it('refreshes a changed collection around the saved entry without resending the expired pin',async()=>{
 vi.mocked(api).mockResolvedValueOnce(page()).mockRejectedValueOnce(new ApiError(409,'Collection changed',{code:'COLLECTION_CHANGED'})).mockResolvedValueOnce(page(0,'v2',998,2))
 const ctx=context(),session=getPreviewSession(ctx);await session.load()
 savePreviewAnchor(ctx,{...item(2),offset:-35,collection_version:'v1'})
 const result=await session.load({offset:50})
 expect(api).toHaveBeenCalledTimes(3);expect(result.located?.entry_id).toBe('attempt:3');expect(result.notice).toBeTruthy()
 const retried=new URL(String(vi.mocked(api).mock.calls[2]![0]),'http://fixture').searchParams
 expect(retried.has('collection_version')).toBe(false);expect(retried.get('locate_entry')).toBe('attempt:3');expect(retried.get('fallback_index')).toBe('2')
 expect(getPreviewAnchor(ctx)?.offset).toBe(-35)
})
it.each([401,409])('does not retry authentication/account-affinity rejection %s as a collection refresh',async(status)=>{
 const detail=status===409?'Account changed. Reload required.':'Authentication credentials were not provided.'
 vi.mocked(api).mockRejectedValueOnce(new ApiError(status,detail,{detail,code:'COLLECTION_CHANGED'}))
 const session=getPreviewSession(context())
 await expect(session.load()).rejects.toMatchObject({status})
 expect(api).toHaveBeenCalledTimes(1);expect(accountPreferences.reset).toHaveBeenCalledOnce();expect(session.cachedCount).toBe(0)
})
it('isolates owner caches and refuses a late response after the active account changes',async()=>{
 const pending=deferred<PreviewPage>();vi.mocked(api).mockResolvedValueOnce(page()).mockReturnValueOnce(pending.promise)
 const ctx=context(),old=getPreviewSession(ctx);await old.load();savePreviewAnchor(ctx,{...item(3),offset:44,collection_version:'v1'})
 const inflight=old.load({offset:50}),rejected=expect(inflight).rejects.toMatchObject({name:'AbortError'})
 accountPreferences.userId.value='different-account'
 const next=getPreviewSession(ctx)
 expect(next).not.toBe(old);expect(next.cachedCount).toBe(0);expect(old.cachedCount).toBe(0);expect(old.get(0)).toBeUndefined();expect(getPreviewAnchor(ctx)).toBeNull()
 pending.resolve(page(50));await rejected
 expect(next.cachedCount).toBe(0)
})

it('waits for a fresh collection snapshot before issuing a concurrent nonfresh request with the accepted version',async()=>{
 vi.mocked(api).mockResolvedValueOnce(page())
 const session=getPreviewSession(context());await session.load()
 const fresh=deferred<PreviewPage>(),nextPage=deferred<PreviewPage>();vi.mocked(api).mockReturnValueOnce(fresh.promise).mockReturnValueOnce(nextPage.promise)
 const a=session.load({fresh:true}),b=session.load({offset:50})
 expect(api).toHaveBeenCalledTimes(2)
 fresh.resolve(page(0,'v2',999));await a
 await vi.waitFor(()=>expect(api).toHaveBeenCalledTimes(3))
 const params=new URL(String(vi.mocked(api).mock.calls[2]![0]),'http://fixture').searchParams
 expect(params.get('collection_version')).toBe('v2')
 nextPage.resolve(page(50,'v2',999));await b
 expect(session.version).toBe('v2');expect(session.count).toBe(999);expect(session.get(0)?.entry_id).toBe('attempt:1');expect(session.get(50)?.index).toBe(50)
})
it('rejects a canceled second consumer without canceling the active first consumer of the same request',async()=>{
 const pending=deferred<PreviewPage>();vi.mocked(api).mockReturnValueOnce(pending.promise)
 const session=getPreviewSession(context()),first=session.load(),controller=new AbortController(),second=session.load({signal:controller.signal})
 const rejected=expect(second).rejects.toMatchObject({name:'AbortError'})
 controller.abort();pending.resolve(page());await first;await rejected
 expect(api).toHaveBeenCalledTimes(1);expect(session.cachedCount).toBe(50)
})
it('does not expose an old account entry through find() after identity changes',async()=>{
 vi.mocked(api).mockResolvedValueOnce(page());const session=getPreviewSession(context());await session.load()
 accountPreferences.userId.value='changed-owner'
 expect(session.find('attempt:1')).toBeUndefined()
})

it('refuses a response that violates the requested collection pin without rolling the cache into that version',async()=>{
 vi.mocked(api).mockResolvedValueOnce(page())
 const session=getPreviewSession(context());await session.load()
 const corrupt=deferred<PreviewPage>(),valid=deferred<PreviewPage>();vi.mocked(api).mockReturnValueOnce(corrupt.promise).mockReturnValueOnce(valid.promise)
 const a=session.load({offset:50}),rejected=expect(a).rejects.toBeDefined(),b=session.load({offset:100})
 corrupt.resolve(page(50,'unexpected-version',999));valid.resolve(page(100,'v1',1000));await rejected;await b
 expect(session.version).toBe('v1');expect(session.count).toBe(1000);expect(session.get(50)).toBeUndefined();expect(session.get(100)?.index).toBe(100)
})
