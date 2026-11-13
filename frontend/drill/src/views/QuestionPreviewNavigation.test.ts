// @vitest-environment jsdom
import { expect, it, vi } from 'vitest'
import ts from 'typescript'
import source from './QuestionView.vue?raw'
import { buildListContext, previewLocation, previewQuestionLocation } from '../lib/listContext'
const ref = <T>(value:T) => ({value})
function handler(start:string,end:string,name:string,scope:object) {
 const raw=source.slice(source.indexOf(start),source.indexOf(end,source.indexOf(start)))
 const js=ts.transpileModule(raw,{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText
 return new Function('scope',`with(scope){${js};return ${name}}`)(scope)
}
const context=buildListContext('attempts',{q:'导数',sort:'oldest'},'/insight?q=导数&questions_page=4')
it('navigates between duplicate history entries without conflating their question UUID',async()=>{
 const next={entry_id:'attempt:2',question_uuid:'same-question',index:1}
 const push=vi.fn().mockResolvedValue(undefined)
 const scope={previewContext:ref(context),previewNavigation:ref({next_entry:next,previous_entry:null}),
  isReaderOpen:()=>false,pendingFullscreenTarget:ref(null),startPageTurnCopy:vi.fn(),cachedQuestion:()=>null,navigationQueryString:()=>'',navigationFrame:ref({}),props:{uuid:'same-question'},router:{push},previewQuestionLocation}
 const navigate=handler('function navigateToQuestion(','\nfunction selectSourceQuestion','navigateToQuestion',scope)
 await navigate('same-question','next')
 expect(push).toHaveBeenCalledWith(previewQuestionLocation(context,next))
 expect(push.mock.calls[0][0].query.entry).toBe('attempt:2')
})
it('never routes a collection next action to a stale or unrelated UUID',()=>{
 const push=vi.fn()
 const scope={previewContext:ref(context),previewNavigation:ref({next_entry:{entry_id:'attempt:2',question_uuid:'correct',index:1}}),isReaderOpen:()=>false,pendingFullscreenTarget:ref(null),startPageTurnCopy:vi.fn(),cachedQuestion:()=>null,navigationQueryString:()=>'',navigationFrame:ref({}),props:{uuid:'old'},router:{push},previewQuestionLocation}
 handler('function navigateToQuestion(','\nfunction selectSourceQuestion','navigateToQuestion',scope)('unrelated','next')
 expect(push).not.toHaveBeenCalled()
})
it('returns to the original preview anchor without replacing it with the last Practice entry',()=>{
 const push=vi.fn()
 handler('function backToEntryPoint()', '\nconst question =','backToEntryPoint',{previewContext:ref(context),router:{push},previewLocation})()
 expect(push).toHaveBeenCalledWith(previewLocation(context))
 expect(push.mock.calls[0][0].query).not.toHaveProperty('entry')
})
it('does not send the serialized list context into the expensive old question-navigation query',()=>{
 const route={query:{list:JSON.stringify(context),entry:'attempt:2',from:'preview',q:'unrelated'}}
 const get=handler('function navigationQuery()', '\nfunction navigationQueryString()', 'navigationQuery',{previewContext:ref(context),router:{currentRoute:ref(route)}})
 expect(get()).toEqual({})
})
it('warms only the actual previous and next collection neighbours',()=>{
 const prefetchQuestion=vi.fn().mockResolvedValue(null),warmQuestionMedia=vi.fn()
 const scope={previewContext:ref(context),navigationQueryString:()=>'',warmQuestionMedia,prefetchQuestion,navigationPrevious:ref('collection-prev'),navigationNext:ref('collection-next')}
 handler('function schedulePrefetch(', '\nasync function load()', 'schedulePrefetch',scope)({uuid:'current',sequential_next_question_uuid:'unrelated-global-next'})
 expect(prefetchQuestion.mock.calls).toEqual([['collection-prev',''],['collection-next','']])
 expect(warmQuestionMedia).toHaveBeenCalledOnce()
})
it('a removed current entry cannot silently attach the open question to its neighbour',async()=>{
 const scope={isPreviewEntry:ref(true),previewNavigationSequence:0,previewNavigation:ref<unknown>(null),previewNavigationError:ref(''),previewContext:ref(context),getPreviewAnchor:()=>({index:237}),getPreviewSession:()=>({load:vi.fn().mockResolvedValue({located:{entry_id:'attempt:99',question_uuid:'different',index:237}})}),route:{query:{entry:'attempt:removed'}},props:{uuid:'current'}}
 await handler('async function loadPreviewNavigation(', '\nconst errorOptions:', 'loadPreviewNavigation',scope)()
 expect(scope.previewNavigation.value).toBeNull()
 expect(scope.previewNavigationError.value).toContain('不在当前题单')
})
function removedScope(locatedIndex:number,uuid='neighbour') {
 const page={count:20,located:{entry_id:'question:next',question_uuid:uuid,index:locatedIndex},next_entry:{entry_id:'question:after-next',question_uuid:'after-next',index:locatedIndex+1},previous_entry:null}
 const scope={isPreviewEntry:ref(true),previewNavigationSequence:0,previewNavigation:ref<unknown>(null),previewNavigationError:ref(''),previewContext:ref(context),getPreviewAnchor:()=>({index:2}),getPreviewSession:()=>({load:vi.fn().mockResolvedValue(page)}),route:{query:{entry:'question:removed',position:'19'}},props:{uuid:'current'}}
 return {scope,page,load:handler('async function loadPreviewNavigation(', '\nconst errorOptions:', 'loadPreviewNavigation',scope)}
}
it('uses the current list ordinal rather than the original browsing anchor after saving removes the current item',async()=>{
 const {scope,load}=removedScope(19)
 await load(undefined,true)
 expect(scope.previewNavigation.value).toMatchObject({next_entry:{entry_id:'question:next',index:19}})
 expect(scope.previewNavigationError.value).toBe('')
})
it('does not wrap backwards when saving removes the final item from the collection',async()=>{
 const {scope,load}=removedScope(18)
 await load(undefined,true)
 expect(scope.previewNavigation.value).toMatchObject({next_entry:null})
})
it('does not substitute a different Attempt with the same UUID when the requested entry was removed',async()=>{
 const {scope,load}=removedScope(19,'current')
 await load()
 expect(scope.previewNavigation.value).toBeNull()
 expect(scope.previewNavigationError.value).toContain('不在当前题单')
})

it('opens scrolling preview at the current question with the configured next mode',()=>{
 const push=vi.fn();const route={fullPath:'/practice/current?document=3',query:{document:'3'}}
 const scope={question:ref({uuid:'current'}),previewContext:ref(null),route,props:{uuid:'current'},router:{push},navigationQuery:()=>({document:'3',type_group:'small'}),effectiveNextMode:ref('overdue'),buildListContext,previewLocation}
 handler('function openScrollingPreview()', '\nconst errorOptions:', 'openScrollingPreview',scope)()
 const target=push.mock.calls[0][0];expect(target.query.question).toBe('current');const list=JSON.parse(target.query.list);expect(list.source).toBe('navigation');expect(list.query).toMatchObject({navigation_anchor:'current',navigation_mode:'overdue',document:'3',type_group:'small'});expect(list.returnTo).toBe(route.fullPath)
})
it('reuses an existing preview list including duplicate entry identity',()=>{
 const push=vi.fn();const scope={question:ref({uuid:'same-question'}),previewContext:ref(context),route:{query:{entry:'attempt:12'}},props:{uuid:'same-question'},router:{push},previewLocation}
 handler('function openScrollingPreview()', '\nconst errorOptions:', 'openScrollingPreview',scope)()
 expect(push).toHaveBeenCalledWith(previewLocation(context,'attempt:12','same-question'))
})
