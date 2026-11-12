export const accentIds = ['blue', 'cyan', 'green', 'lime', 'yellow', 'orange', 'pink', 'magenta', 'purple', 'monochrome'] as const
export type Accent = typeof accentIds[number]
export type Appearance = 'system' | 'light' | 'dark'
export type ResolvedScheme = 'light' | 'dark'
export interface VisualPreferences { version: 1; appearance: Appearance; accent: Accent }
interface ColorSet { solid: string; ink: string; onSolid: string }
export const accents: Record<Accent, { label: string; light: ColorSet; dark: ColorSet }> = {
  blue: { label: 'Blue', light: { solid: '#2563EB', ink: '#1D4ED8', onSolid: '#FFFFFF' }, dark: { solid: '#8AB4FF', ink: '#8AB4FF', onSolid: '#141414' } },
  cyan: { label: 'Cyan', light: { solid: '#0E7490', ink: '#155E75', onSolid: '#FFFFFF' }, dark: { solid: '#67D5E8', ink: '#67D5E8', onSolid: '#141414' } },
  green: { label: 'Green', light: { solid: '#15803D', ink: '#166534', onSolid: '#FFFFFF' }, dark: { solid: '#72D59B', ink: '#72D59B', onSolid: '#141414' } },
  lime: { label: 'Lime', light: { solid: '#B5D96A', ink: '#3F6212', onSolid: '#141414' }, dark: { solid: '#B5D96A', ink: '#B5D96A', onSolid: '#141414' } },
  yellow: { label: 'Yellow', light: { solid: '#F4D06F', ink: '#855700', onSolid: '#141414' }, dark: { solid: '#F4D06F', ink: '#F4D06F', onSolid: '#141414' } },
  orange: { label: 'Orange', light: { solid: '#B54708', ink: '#9A3412', onSolid: '#FFFFFF' }, dark: { solid: '#FFB375', ink: '#FFB375', onSolid: '#141414' } },
  pink: { label: 'Pink', light: { solid: '#BE185D', ink: '#9D174D', onSolid: '#FFFFFF' }, dark: { solid: '#F6A4C7', ink: '#F6A4C7', onSolid: '#141414' } },
  magenta: { label: 'Magenta', light: { solid: '#A21CAF', ink: '#86198F', onSolid: '#FFFFFF' }, dark: { solid: '#E9A0EF', ink: '#E9A0EF', onSolid: '#141414' } },
  purple: { label: 'Purple', light: { solid: '#7E22CE', ink: '#6B21A8', onSolid: '#FFFFFF' }, dark: { solid: '#C2A6FF', ink: '#C2A6FF', onSolid: '#141414' } },
  monochrome: { label: 'Black / Monochrome', light: { solid: '#262626', ink: '#262626', onSolid: '#FFFFFF' }, dark: { solid: '#EDEDED', ink: '#EDEDED', onSolid: '#141414' } },
}
export function rgb(hex: string) { return [1, 3, 5].map((offset) => parseInt(hex.slice(offset, offset + 2), 16)).join(', ') }
export function blendHex(a: string, b: string, amount: number) { return '#' + [1, 3, 5].map(i => Math.round(parseInt(a.slice(i, i + 2), 16) * (1 - amount) + parseInt(b.slice(i, i + 2), 16) * amount).toString(16).padStart(2, '0')).join('') }
export function colorVariables(accent: Accent, scheme: ResolvedScheme): Record<string, string> {
  const colors = accents[accent][scheme]
  const overlay = scheme === 'light' && colors.onSolid === '#FFFFFF' ? '#000000' : colors.onSolid
  return { '--accent-solid': colors.solid, '--accent-solid-hover': blendHex(colors.solid, overlay, .08), '--accent-solid-pressed': blendHex(colors.solid, overlay, .12), '--accent-ink': colors.ink, '--accent-on-solid': colors.onSolid, '--accent-ink-rgb': rgb(colors.ink), '--accent-solid-rgb': rgb(colors.solid) }
}
export function paletteCss() {
  const declarations = (id: Accent, scheme: ResolvedScheme) => Object.entries(colorVariables(id, scheme)).map(([key, value]) => `${key}:${value}`).join(';')
  return `:root{${declarations('blue', 'light')}}\n` + accentIds.map((id) => `[data-accent="${id}"]{${declarations(id, 'light')}}\n[data-color-scheme="dark"][data-accent="${id}"]{${declarations(id, 'dark')}}`).join('\n') + `\n@media(prefers-color-scheme:dark){:root:not([data-color-scheme]){${declarations('blue', 'dark')}}}`
}
