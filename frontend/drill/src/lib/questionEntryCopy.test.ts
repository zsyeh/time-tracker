// @vitest-environment jsdom
import { beforeEach, expect, it, vi } from 'vitest'
const state=vi.hoisted(()=>({owner:{value:'owner'},mode:{value:'image'},scale:{value:2}}))
vi.mock('../../../shared/preferences/store',()=>({accountPreferences:{userId:state.owner}}))
vi.mock('./practicePreferences',()=>({usePracticePreferences:()=>({pageTurnCopyMode:state.mode,imageCopyScale:state.scale})}))
vi.mock('./workspace',()=>({fetchQuestion:vi.fn(async(uuid:string)=>({uuid,question_assets:[{url:'/asset/'+uuid}]}))}))
vi.mock('./sourcePractice',()=>({sourcePracticeTarget:vi.fn(()=>null)}))
vi.mock('./runtimePath',()=>({withWorkspacePrefix:(url:string)=>'/drill'+url}))
vi.mock('./imageClipboard',()=>({copyImagesToClipboard:vi.fn(async(urls:Promise<string[]>,_scale:number)=>{await urls;return{limited:false}})}))
vi.mock('./share',()=>({createAndCopyShareOnGesture:vi.fn(async(endpoint:Promise<string>)=>{await endpoint;return{copied:true}})}))
import { armQuestionEntryCopy, takeQuestionEntryCopy } from './questionEntryCopy'
import { fetchQuestion } from './workspace'
import { copyImagesToClipboard } from './imageClipboard'
import { createAndCopyShareOnGesture } from './share'
beforeEach(()=>{vi.clearAllMocks();state.owner.value='owner';state.mode.value='image';state.scale.value=2})
it('starts a promised ClipboardItem copy before the entry detail request finishes and keeps the chosen multiplier',async()=>{
 let resolve!:(value:Awaited<ReturnType<typeof fetchQuestion>>)=>void;vi.mocked(fetchQuestion).mockImplementationOnce(()=>new Promise(r=>{resolve=r}) as ReturnType<typeof fetchQuestion>)
 const task=armQuestionEntryCopy('q',{document:'5'})!;expect(copyImagesToClipboard).toHaveBeenCalledOnce();expect(copyImagesToClipboard).toHaveBeenCalledWith(expect.any(Promise),2)
 resolve({uuid:'q',question_assets:[{url:'/asset/q'}]} as Awaited<ReturnType<typeof fetchQuestion>>);expect((await task.result).copied).toBe(true);expect(takeQuestionEntryCopy('q')).toBe(task);expect(takeQuestionEntryCopy('q')).toBeNull()
})
it('does nothing when auto-copy is disabled or the user is not bound',()=>{state.mode.value='off';expect(armQuestionEntryCopy('q',{})).toBeNull();expect(fetchQuestion).not.toHaveBeenCalled();state.mode.value='image';state.owner.value='';expect(armQuestionEntryCopy('q',{})).toBeNull()})
it('copies links too and strips serialized preview context from the detail query',async()=>{state.mode.value='link';const task=armQuestionEntryCopy('q',{from:'preview',list:'serialized-context'})!;expect(createAndCopyShareOnGesture).toHaveBeenCalledOnce();await task.result;expect(fetchQuestion).toHaveBeenCalledWith('q','',true);expect(copyImagesToClipboard).not.toHaveBeenCalled()})
it('turns a blocked entry clipboard into a recoverable result rather than rejecting navigation',async()=>{vi.mocked(copyImagesToClipboard).mockRejectedValueOnce(new DOMException('blocked','NotAllowedError'));const result=await armQuestionEntryCopy('q',{})!.result;expect(result.copied).toBe(false);expect(result.message).toContain('重试')})
