import { computed, readonly, ref } from 'vue'
import type { Accent, Appearance } from './palette'
import { applyVisualPreferences, persistVisualPreferences, readVisualPreferences, VISUAL_KEY } from './resolve'
export { accents, accentIds } from './palette'
export type { Accent, Appearance } from './palette'
const initial = readVisualPreferences()
const appearance = ref<Appearance>(initial.appearance)
const accent = ref<Accent>(initial.accent)
const resolved = ref(applyVisualPreferences(initial))
let initialized = false
function apply(persist = false) {
  const preferences = { version: 1 as const, appearance: appearance.value, accent: accent.value }
  resolved.value = applyVisualPreferences(preferences)
  if (persist) persistVisualPreferences(preferences)
  if (typeof window !== 'undefined') window.dispatchEvent(new CustomEvent('learning:appearance-changed', { detail: preferences }))
}
export function setAppearance(value: Appearance) { if (!['system', 'light', 'dark'].includes(value)) return; appearance.value = value; apply(true) }
export function setAccent(value: Accent) { if (!(value in accents)) return; accent.value = value; apply(true) }
import { accents } from './palette'
export function initializeAppearance() {
  if (initialized || typeof window === 'undefined') return
  initialized = true
  apply(true)
  const media = window.matchMedia?.('(prefers-color-scheme: dark)')
  const followSystem = () => { if (appearance.value === 'system') apply() }
  media?.addEventListener?.('change', followSystem)
  const refresh = () => { const next = readVisualPreferences(); appearance.value = next.appearance; accent.value = next.accent; apply() }
  window.addEventListener('storage', (event) => { if (event.key === VISUAL_KEY) refresh() })
  window.addEventListener('pageshow', refresh)
  window.addEventListener('focus', refresh)
}
export function useAppearance() {
  initializeAppearance()
  return { appearance: readonly(appearance), accent: readonly(accent), resolved: readonly(resolved), scheme: computed(() => resolved.value), setAppearance, setAccent }
}
