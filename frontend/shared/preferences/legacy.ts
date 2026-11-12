import { validPreference, type PreferenceKey, type PreferenceValues } from './schema'
// Legacy keys have no account identity. Never import automatically into whichever
// account happens to log in next; offer an explicit, one-time migration instead.
export function readLegacyPreferences():Partial<PreferenceValues> {
 const result:Partial<PreferenceValues>={}
 const keys:Record<string,PreferenceKey>={'drill.next-mode.v1':'practice.next_mode','drill.review-auto-next.v1':'practice.review_auto_next','drill.mastered-auto-next.v1':'practice.mastered_auto_next','drill.page-turn-copy.v1':'practice.drill.copy_mode','ei.page-turn-copy.v1':'practice.ei.copy_mode'}
 for(const [old,key] of Object.entries(keys))try{const raw=localStorage.getItem(old);if(raw===null)continue;const value=raw==='true'?true:raw==='false'?false:raw;if(validPreference(key,value))Object.assign(result,{[key]:value})}catch{}
 for(const workspace of ['drill','ei'] as const)try{
  const current=localStorage.getItem(`practice.trend.settings.v2.${workspace}`)
  const old=current===null?localStorage.getItem(`practice.trend.settings.v1.${workspace}`):null
  const value=JSON.parse(current??old??'null')
  if(current===null && value?.deadline==='2026-11-22')value.deadline='2026-11-21'
  const key=`progress.${workspace}` as const
  if(validPreference(key,value))Object.assign(result,{[key]:value})
 }catch{}
 return result
}
export function clearLegacyPreferences(){for(const workspace of ['drill','ei'])for(const version of ['v1','v2'])try{localStorage.removeItem(`practice.trend.settings.${version}.${workspace}`)}catch{};for(const workspace of ['drill','ei'])for(const setting of ['next-mode','review-auto-next','mastered-auto-next','page-turn-copy'])try{localStorage.removeItem(`${workspace}.${setting}.v1`)}catch{}}
