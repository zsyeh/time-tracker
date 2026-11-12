import { readPreferenceBootstrap } from '../preferences/bootstrap'
import { accentIds, colorVariables, type Accent, type Appearance, type ResolvedScheme, type VisualPreferences } from './palette'
export const VISUAL_KEY = 'learning.ui.visual.v1'
export const VISUAL_COOKIE = 'learning_ui_visual_v1'
const oldAccents: Record<string, Accent> = { violet: 'purple', coolapk: 'green', bilibili: 'pink', meituan: 'yellow', apple: 'monochrome', youtube: 'pink' }
export function cookieValue(name: string): string | null {
  if (typeof document === 'undefined') return null
  try {
    const value = document.cookie.split(';').map((item) => item.trim()).find((item) => item.startsWith(`${name}=`))
    return value ? decodeURIComponent(value.slice(name.length + 1)) : null
  } catch { return null }
}
export function localValue(name: string): string | null { try { return localStorage.getItem(name) } catch { return null } }
export function parseVisual(value: string | null): VisualPreferences | null {
  if (!value) return null
  try {
    const parsed = JSON.parse(value)
    if (parsed?.version === 1 && ['system', 'light', 'dark'].includes(parsed.appearance) && accentIds.includes(parsed.accent)) return { version: 1, appearance: parsed.appearance, accent: parsed.accent }
  } catch { /* Untrusted device preferences never block boot. */ }
  return null
}
export function readVisualPreferences(): VisualPreferences {
  const bootstrap = readPreferenceBootstrap()
  if (bootstrap) return { version:1, appearance:bootstrap.snapshot?.values.appearance || 'system', accent:bootstrap.snapshot?.values.accent || 'blue' }
  const current = parseVisual(cookieValue(VISUAL_COOKIE)) || parseVisual(localValue(VISUAL_KEY))
  if (current) return current
  const oldScheme = cookieValue('learning_os_color_scheme') || localValue('learning-os-color-scheme')
  return { version: 1, appearance: oldScheme === 'light' || oldScheme === 'dark' ? oldScheme : 'system', accent: oldAccents[localValue('learning-os-theme') || ''] || 'blue' }
}
export function resolveScheme(appearance: Appearance, systemDark: boolean): ResolvedScheme { return appearance === 'system' ? systemDark ? 'dark' : 'light' : appearance }
export function applyVisualPreferences(preferences: VisualPreferences) {
  if (typeof document === 'undefined') return 'light' as const
  const scheme = resolveScheme(preferences.appearance, typeof matchMedia !== 'undefined' && matchMedia('(prefers-color-scheme: dark)').matches)
  const root = document.documentElement
  root.dataset.appearance = preferences.appearance
  root.dataset.colorScheme = scheme
  root.dataset.accent = preferences.accent
  root.removeAttribute('data-theme')
  root.style.colorScheme = scheme
  Object.entries(colorVariables(preferences.accent, scheme)).forEach(([name, value]) => root.style.setProperty(name, value))
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', scheme === 'dark' ? '#141414' : '#ffffff')
  return scheme
}
export function persistVisualPreferences(preferences: VisualPreferences) {
  const value = JSON.stringify(preferences)
  try { localStorage.setItem(VISUAL_KEY, value) } catch { /* Device storage can be disabled. */ }
  if (typeof document === 'undefined' || typeof location === 'undefined') return
  const domain = location.hostname === 'ehzsy.site' || location.hostname.endsWith('.ehzsy.site') ? '; Domain=.ehzsy.site' : ''
  try { document.cookie = `${VISUAL_COOKIE}=${encodeURIComponent(value)}; Path=/; Max-Age=31536000; SameSite=Lax${domain}${location.protocol === 'https:' ? '; Secure' : ''}` } catch { /* Use memory state when cookies are blocked. */ }
}
