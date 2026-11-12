import { computed, ref } from 'vue'
import type { Accent, Appearance } from './palette'
import { applyVisualPreferences } from './resolve'
import { useAccountPreferences } from '../preferences/store'
export { accents, accentIds } from './palette'
export type { Accent, Appearance } from './palette'
let initialized=false
const systemDark=ref(typeof matchMedia!=='undefined'&&matchMedia('(prefers-color-scheme: dark)').matches)
export function setAppearance(value:Appearance){useAccountPreferences().set('appearance',value)}
export function setAccent(value:Accent){useAccountPreferences().set('accent',value)}
export function initializeAppearance(){
  if(initialized||typeof window==='undefined')return
  initialized=true
  const media=window.matchMedia?.('(prefers-color-scheme: dark)')
  media?.addEventListener?.('change',()=>{
    systemDark.value=media.matches
    const values=useAccountPreferences().values
    applyVisualPreferences({version:1,appearance:values.appearance,accent:values.accent})
  })
}
export function useAppearance(){
  initializeAppearance()
  const store=useAccountPreferences()
  const resolved=computed(()=>store.values.appearance==='system'?(systemDark.value?'dark':'light'):store.values.appearance)
  return {appearance:computed(()=>store.values.appearance),accent:computed(()=>store.values.accent),resolved,scheme:resolved,setAppearance,setAccent}
}
