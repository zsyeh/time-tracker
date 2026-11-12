import { computed, type Ref } from 'vue'
import { useAccountPreferences } from '../../../shared/preferences/store'
import type { NextQuestionMode } from './questionNavigation'
import { runtimeWorkspace } from './runtimePath'
export type PageTurnCopyMode='off'|'link'|'image'
type Workspace='drill'|'ei'
type PracticePreferences={nextMode:Ref<NextQuestionMode>;pageTurnCopyMode:Ref<PageTurnCopyMode>;reviewAutoNext:Ref<boolean>;masteredAutoNext:Ref<boolean>}
const workspaces=new Map<Workspace,PracticePreferences>()
export function usePracticePreferences(workspace:Workspace=runtimeWorkspace):PracticePreferences {
 const existing=workspaces.get(workspace);if(existing)return existing
 const store=useAccountPreferences()
 const value={nextMode:computed({get:()=>store.values['practice.next_mode'],set:value=>store.set('practice.next_mode',value)}),reviewAutoNext:computed({get:()=>store.values['practice.review_auto_next'],set:value=>store.set('practice.review_auto_next',value)}),masteredAutoNext:computed({get:()=>store.values['practice.mastered_auto_next'],set:value=>store.set('practice.mastered_auto_next',value)}),pageTurnCopyMode:computed({get:()=>store.values[`practice.${workspace}.copy_mode`],set:value=>store.set(`practice.${workspace}.copy_mode`,value)})}
 workspaces.set(workspace,value);return value
}
