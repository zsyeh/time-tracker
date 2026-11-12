import { validSnapshot, type PreferenceSnapshot } from './schema'
export type PreferenceBootstrap = { user_id: string|null; snapshot: PreferenceSnapshot|null }
export function readPreferenceBootstrap(): PreferenceBootstrap|null {
  if (typeof document === 'undefined') return null
  try {
    const node = document.getElementById('learning-user-preferences')
    if (!node) return null
    const value = JSON.parse(node.textContent || 'null')
    if (value?.user_id == null) return { user_id:null, snapshot:null }
    if (typeof value.user_id === 'string' && validSnapshot(value.snapshot)) return value
  } catch { /* Malformed bootstrap cannot block practice. */ }
  return null
}
