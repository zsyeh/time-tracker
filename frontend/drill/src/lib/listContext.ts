import { runtimeWorkspace } from './runtimePath'
export const listSources=['practice','heatmap','attempts','notes','favorite','review_later','selected','diagnostics','paper','errata'] as const
export type ListSource=typeof listSources[number]
export type ListContext={version:1;workspace:'drill'|'ei';source:ListSource;query:Record<string,string>;returnTo:string}
export type PreviewAsset={id:number;url:string;width:number;height:number;position?:number}
export type PreviewNeighbor={entry_id:string;question_uuid:string;index:number}
export type PreviewItem=PreviewNeighbor & {label:string;document:string;topic:string;state:string;is_favorite?:boolean;review_later?:boolean;preview:{question_markdown:string;assets:PreviewAsset[];source_page?:boolean};attempt?:{id:number;result:string;created_at:string};note_excerpt?:string}
export type PreviewPage={count:number;offset:number;limit:50;has_more:boolean;collection_version:string;located:PreviewNeighbor|null;notice?:string;results:PreviewItem[];previous_entry:PreviewNeighbor|null;next_entry:PreviewNeighbor|null}
export type PreviewAnchor=PreviewNeighbor & {offset:number;collection_version:string;scrollTop?:number}
const filterKeys=new Set(['unattempted','past_exam','search_version','document','topic','source_category','type_group','exam_type','q','sort','status','favorite','review_later','marker','include_structure','collection','bucket','tier','kind','combined','state','scope','course','material','mode','start','end','error','has_note','queue','paper','paper_uuid','all'])
export function safeListReturn(value:unknown){
 if(typeof value!=='string'||value.length>4096||/[\u0000-\u001f]/.test(value)||!/^\/(?:practice|favorites|review-later|insight|heatmap|selected-heatmap|core-heatmap|circuit-selected|signal-selected|analog-selected|digital-selected|communication-selected|diagnostic-queue|diagnostics|cockpit|errata|papers|feel)(?:[/?#]|$)/.test(value))return '/practice'
 return value
}
export function buildListContext(source:ListSource,query:Record<string,unknown>,returnTo:string):ListContext{
 const clean:Record<string,string>={}
 for(const [key,raw] of Object.entries(query)){
  if(!filterKeys.has(key)||raw===null||raw===undefined||Array.isArray(raw))continue
  const value=String(raw).trim();if(value&&value.length<=256&&!/[\u0000-\u001f]/.test(value))clean[key]=value
 }
 return{version:1,workspace:runtimeWorkspace,source,query:Object.fromEntries(Object.entries(clean).sort(([a],[b])=>a.localeCompare(b))),returnTo:safeListReturn(returnTo)}
}
export function parseListContext(raw:unknown):ListContext|null{
 if(typeof raw!=='string'||raw.length>8192)return null
 try{
  const value=JSON.parse(raw)
  if(value?.version!==1||value.workspace!==runtimeWorkspace||!listSources.includes(value.source)||!value.query||typeof value.query!=='object'||Array.isArray(value.query))return null
  return buildListContext(value.source,value.query,value.returnTo)
 }catch{return null}
}
export function listContextKey(context:ListContext){return JSON.stringify({workspace:context.workspace,source:context.source,query:Object.fromEntries(Object.entries(context.query).sort(([a],[b])=>a.localeCompare(b)))})}
export function previewLocation(context:ListContext,entryId?:string,questionUuid?:string){return{path:'/preview',query:{list:JSON.stringify(context),...(entryId?{entry:entryId}:{}),...(questionUuid?{question:questionUuid}:{})}}}
export function previewQuestionLocation(context:ListContext,item:PreviewNeighbor){return{path:`/practice/${item.question_uuid}`,query:{list:JSON.stringify(context),entry:item.entry_id,position:String(item.index),from:'preview'}}}
