import { validPreference, type PreferenceKey, type PreferenceValues } from './schema'
// Legacy keys have no account identity. Never import automatically into whichever
// account happens to log in next; offer an explicit, one-time migration instead.
export function readLegacyPreferences():Partial<PreferenceValues> {
 const result:Partial<PreferenceValues>={}
 const keys:Record<string,PreferenceKey>={'drill.next-mode.v1':'practice.next_mode','drill.review-auto-next.v1':'practice.review_auto_next','drill.mastered-auto-next.v1':'practice.mastered_auto_next','drill.page-turn-copy.v1':'practice.drill.copy_mode','ei.page-turn-copy.v1':'practice.ei.copy_mode'}
 for(const [old,key] of Object.entries(keys))try{const raw=localStorage.getItem(old);if(raw===null)continue;const value=raw==='true'?true:raw==='false'?false:raw;if(validPreference(key,value))Object.assign(result,{[key]:value})}catch{}
 return result
}
export function clearLegacyPreferences(){for(const workspace of ['drill','ei'])for(const setting of ['next-mode','review-auto-next','mastered-auto-next','page-turn-copy'])try{localStorage.removeItem(`${workspace}.${setting}.v1`)}catch{}}
