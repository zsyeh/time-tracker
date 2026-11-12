import { effectScope, ref, watch, type Ref } from 'vue'
import type { NextQuestionMode } from './questionNavigation'
import { runtimeWorkspace } from './runtimePath'

export type PageTurnCopyMode = 'off' | 'link' | 'image'
type Workspace = 'drill' | 'ei'
type PracticePreferences = {
  nextMode: Ref<NextQuestionMode>
  pageTurnCopyMode: Ref<PageTurnCopyMode>
  reviewAutoNext: Ref<boolean>
  masteredAutoNext: Ref<boolean>
}
function read(key: string) {
  try { return localStorage.getItem(key) } catch { return null }
}
function persisted<T extends string | boolean>(key: string, value: T) {
  const state = ref(value) as Ref<T>
  // Detached scope: page and Settings share the same refs after either route unmounts.
  effectScope(true).run(() => watch(state, next => {
    try { localStorage.setItem(key, String(next)) } catch { /* Device storage is optional. */ }
  }, { flush: 'sync' }))
  return state
}
let common: Omit<PracticePreferences, 'pageTurnCopyMode'> | undefined
const workspaces = new Map<Workspace, PracticePreferences>()

export function usePracticePreferences(workspace: Workspace = runtimeWorkspace): PracticePreferences {
  const existing = workspaces.get(workspace)
  if (existing) return existing
  if (!common) {
    const storedMode = read('drill.next-mode.v1')
    const nextMode: NextQuestionMode = storedMode === 'overdue' || storedMode === 'review' || storedMode === 'unattempted' ? storedMode : 'sequential'
    // These three legacy keys are intentionally shared by Drill/EI. Do not migrate
    // them to workspace keys or reset an existing user's automatic-next behavior.
    common = {
      nextMode: persisted('drill.next-mode.v1', nextMode),
      reviewAutoNext: persisted('drill.review-auto-next.v1', read('drill.review-auto-next.v1') === 'true'),
      masteredAutoNext: persisted('drill.mastered-auto-next.v1', read('drill.mastered-auto-next.v1') !== 'false'),
    }
  }
  const key = `${workspace}.page-turn-copy.v1`
  const storedCopy = read(key)
  const value: PageTurnCopyMode = storedCopy === 'link' || storedCopy === 'image' ? storedCopy : 'off'
  const preferences = { ...common, pageTurnCopyMode: persisted(key, value) }
  workspaces.set(workspace, preferences)
  return preferences
}
