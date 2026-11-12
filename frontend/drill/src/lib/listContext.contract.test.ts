// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { buildListContext, listContextKey, parseListContext, previewLocation, previewQuestionLocation, safeListReturn } from './listContext'
const runtime=vi.hoisted(()=>({workspace:'drill' as 'drill'|'ei'}))
vi.mock('./runtimePath',()=>({get runtimeWorkspace(){return runtime.workspace}}))
afterEach(()=>{runtime.workspace='drill'})
it('preserves all source filters and original return path while stripping pagination, pins and source routing hints',()=>{
 const query={q:'偏导数 Fourier',document:'12',topic:'4',source_category:'past_exam',type_group:'small',exam_type:'choice',status:'review',favorite:'1',review_later:'1',marker:'rusty',include_structure:'1',collection:'selected',bucket:'fourier',tier:'core',kind:'calculation',combined:'1',state:'unattempted',scope:'past_exam',course:'signal',material:'ready',mode:'questions',start:'2026-11-01',end:'2026-11-12',error:'B2',has_note:'1',queue:'due',paper_uuid:'synthetic-paper',sort:'relevance',page:'3',index_version:'old:1',search_version:'2',from:'selected-heatmap',unknown:'drop'}
 const returnTo='/practice?q=偏导数&page=3&from=selected-heatmap'
 const context=buildListContext('practice',query,returnTo)
 expect(context.returnTo).toBe(returnTo)
 for(const key of ['page','index_version','from','unknown'])expect(context.query).not.toHaveProperty(key)
 for(const [key,value]of Object.entries(query).filter(([key])=>!['page','index_version','from','unknown'].includes(key)))expect(context.query[key]).toBe(value)
 expect(parseListContext(JSON.stringify(context))).toEqual(context)
})
it('keeps exact history sorting/filter semantics and separate source identities',()=>{
 const query={q:'saved note',sort:'oldest',start:'2026-10-01',end:'2026-11-01',error:'C1',has_note:'1',state:'review',questions_page:'3',notes_page:'2'}
 const context=buildListContext('attempts',query,'/insight?questions_page=3&notes_page=2')
 expect(context.query).toMatchObject({q:'saved note',sort:'oldest',start:'2026-10-01',end:'2026-11-01',error:'C1',has_note:'1',state:'review'})
 expect(context.query).not.toHaveProperty('questions_page');expect(context.query).not.toHaveProperty('notes_page')
 expect(listContextKey(context)).not.toBe(listContextKey({...context,source:'notes'}))
})
it('uses semantic filter order for cache keys without merging Drill/EI, sources or filters',()=>{
 const a=buildListContext('favorite',{q:'导数',status:'review'},'/favorites?page=2')
 const b=buildListContext('favorite',{status:'review',q:'导数'},'/favorites?page=3')
 expect(listContextKey(a)).toBe(listContextKey(b))
 expect(listContextKey(a)).not.toBe(listContextKey({...a,workspace:'ei'}))
 expect(listContextKey(a)).not.toBe(listContextKey({...a,source:'review_later'}))
 expect(listContextKey(a)).not.toBe(listContextKey({...a,query:{q:'隐函数',status:'review'}}))
})
it('keeps duplicate attempt identity separate from the question UUID on preview and practice routes',()=>{
 const context=buildListContext('attempts',{},'/insight')
 const first=previewQuestionLocation(context,{entry_id:'attempt:11',question_uuid:'same-question',index:0})
 const second=previewQuestionLocation(context,{entry_id:'attempt:12',question_uuid:'same-question',index:1})
 expect(first.path).toBe(second.path);expect(first.query.entry).not.toBe(second.query.entry)
 expect(first.query.from).toBe('preview')
 expect(previewLocation(context,'attempt:12','same-question').query).toMatchObject({entry:'attempt:12',question:'same-question'})
})
it('rejects malformed and cross-workspace contexts and never accepts external return locations',()=>{
 const context=buildListContext('practice',{},'/practice')
 for(const bad of [null,'broken','{}',JSON.stringify({...context,version:2}),JSON.stringify({...context,workspace:'ei'}),JSON.stringify({...context,source:'unknown'}),JSON.stringify({...context,query:[]})])expect(parseListContext(bad)).toBeNull()
 for(const bad of ['https://example.com','//example.com','javascript:alert(1)','/accounts/logout/','/practice\n'])expect(safeListReturn(bad)).toBe('/practice')
 runtime.workspace='ei'
 expect(buildListContext('selected',{collection:'circuit_selected'},'/circuit-selected').workspace).toBe('ei')
})
