import type { Accent, Appearance } from '../appearance/palette'
export type Workspace = 'timer' | 'drill' | 'ei'
export const fontScales = { compact: .9, small: .95, default: 1, large: 1.05, 'extra-large': 1.1 } as const
export type FontSize = keyof typeof fontScales
export const sidebarIds = {
  timer: ['today','trends','sessions','issues','subject-math','subject-english','subject-major','subject-training'],
  drill: ['selected-heatmap','insight','progress','practice','diagnostics','activity','book-activity','heatmap','papers','favorites','review-later','feel','errata'],
  ei: ['core-heatmap','insight','progress','cockpit','practice','diagnostics','circuit-selected','signal-selected','signal-formulas','analog-selected','digital-selected','communication-selected','selected-pdf-pages','activity','book-activity','heatmap','papers','favorites','review-later','feel','errata'],
} as const
export type SidebarConfig = { order: string[]; hidden: string[]; collapsed_groups: string[] }
export type FilterPreset = { id: string; name: string; query: Record<string,string> }
export type GoalSettings = { target: number; deadline: string }
export type PreferenceValues = {
  appearance: Appearance; accent: Accent; font: FontSize; language: 'en'|'zh-CN'|'ja'
  'sidebar.timer': SidebarConfig; 'sidebar.drill': SidebarConfig; 'sidebar.ei': SidebarConfig
  'filters.drill': FilterPreset[]; 'filters.ei': FilterPreset[]
  'progress.drill': GoalSettings; 'progress.ei': GoalSettings
  'practice.next_mode': 'sequential'|'overdue'|'review'|'unattempted'
  'practice.review_auto_next': boolean; 'practice.mastered_auto_next': boolean
  'practice.drill.copy_mode': 'off'|'link'|'image'; 'practice.ei.copy_mode': 'off'|'link'|'image'
}
export type PreferenceKey = keyof PreferenceValues
export type PreferenceSnapshot = { schema_version: 1; revision: number; values: PreferenceValues; field_revisions: Partial<Record<PreferenceKey,number>>; updated_at?: string|null }
export function defaultSidebar(workspace: Workspace): SidebarConfig {
  const ids = [...sidebarIds[workspace]]
  return { order: ids, hidden: ids.slice(workspace === 'drill' ? 3 : 4), collapsed_groups: [] }
}
export function preferenceDefaults(): PreferenceValues {
  return { appearance:'system', accent:'blue', font:'small', language:'en',
    'sidebar.timer':defaultSidebar('timer'),'sidebar.drill':defaultSidebar('drill'),'sidebar.ei':defaultSidebar('ei'),
    'filters.drill':[],'filters.ei':[],'practice.next_mode':'sequential','practice.review_auto_next':false,'practice.mastered_auto_next':true,
    'practice.drill.copy_mode':'off','practice.ei.copy_mode':'off',
    'progress.drill':{ target:24, deadline:'2026-11-21' }, 'progress.ei':{ target:11, deadline:'2026-11-21' } }
}
/** Unknown future fields may coexist, but every field this client renders must be valid. */
export function validSnapshot(value: unknown): value is PreferenceSnapshot {
  if (!record(value) || value.schema_version !== 1 || !safeRevision(value.revision)
    || !record(value.values) || !record(value.field_revisions)) return false
  const values = value.values
  const revision = value.revision
  if (!Object.keys(preferenceDefaults()).every(key => own(values, key) && validPreference(key, values[key]))) return false
  if (!Object.values(value.field_revisions).every(item => safeRevision(item) && item <= revision)) return false
  if (own(value, 'updated_at') && value.updated_at !== null && typeof value.updated_at !== 'string') return false
  try { JSON.stringify(value) } catch { return false }
  return true
}

const preferenceEnums: Partial<Record<PreferenceKey, readonly string[]>> = {
  appearance: ['system', 'light', 'dark'],
  accent: ['blue', 'cyan', 'green', 'lime', 'yellow', 'orange', 'pink', 'magenta', 'purple', 'monochrome'],
  font: Object.keys(fontScales), language: ['en', 'zh-CN', 'ja'],
  'practice.next_mode': ['sequential', 'overdue', 'review', 'unattempted'],
  'practice.drill.copy_mode': ['off', 'link', 'image'],
  'practice.ei.copy_mode': ['off', 'link', 'image'],
}
const filterEnums: Record<string, readonly string[]> = {
  source_category: ['past_exam', 'adapted_exam', 'mock_exam', 'workbook', 'competition', 'other_practice', 'unclassified'],
  type_group: ['small', 'large', 'short_answer', 'unknown'],
  exam_type: ['choice', 'fill', 'judgment', 'short_answer', 'large', 'unknown'],
  status: ['all', 'unattempted', 'mastered', 'review', 'overdue'],
  marker: ['overconfident', 'concept_gap', 'rusty', 'forgotten'],
  course:['circuit','signal','analog','digital','communication'],material:['ready'],tier:['core','advanced','foundation','cross'],kind:['analysis','design','calculation','concept'],combined:['1'],state:['unattempted','mastered','review'],scope:['all','past_exam','mock_exam'],
  sort: ['relevance', 'source'], favorite: ['1'], review_later: ['1'], include_structure: ['1'],
}
const filterKeys = new Set([...Object.keys(filterEnums), 'q', 'document', 'topic', 'collection', 'bucket'])
const collectionIds = {
  drill: ['selected'],
  ei: ['circuit_selected', 'signal_selected', 'analog_selected', 'digital_selected', 'communication_selected', 'core_selected'],
} as const
const dangerousKeys = new Set(['__proto__', 'constructor', 'prototype'])
const own = (object: object, key: PropertyKey) => Object.prototype.hasOwnProperty.call(object, key)
function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    && (Object.getPrototypeOf(value) === Object.prototype || Object.getPrototypeOf(value) === null)
    && !Object.keys(value).some(key => dangerousKeys.has(key))
}
function exactKeys(value: Record<string, unknown>, keys: readonly string[]) {
  return Object.keys(value).length === keys.length && keys.every(key => own(value, key))
}
function safeRevision(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0
}
function boundedIds(value: unknown, allowed: readonly string[]): value is string[] {
  return Array.isArray(value) && value.length <= allowed.length
    && value.every(id => typeof id === 'string' && allowed.includes(id))
    && new Set(value).size === value.length
}
const textLength = (value: string) => Array.from(value).length
const controls = /[\u0000-\u001f]/
function validSidebar(value: unknown, workspace: Workspace) {
  return record(value) && exactKeys(value, ['order', 'hidden', 'collapsed_groups'])
    && boundedIds(value.order, sidebarIds[workspace]) && boundedIds(value.hidden, sidebarIds[workspace])
    && boundedIds(value.collapsed_groups, ['primary', 'tools', 'subjects'])
}
function validFilterQuery(value: unknown, workspace: 'drill' | 'ei') {
  if (!record(value)) return false
  for (const [key, raw] of Object.entries(value)) {
    if (!filterKeys.has(key) || typeof raw !== 'string' || textLength(raw) > 256 || controls.test(raw)) return false
    const text = raw.trim()
    if (!text) continue
    if (key === 'q' && textLength(text) > 120) return false
    if (own(filterEnums, key) && !filterEnums[key]!.includes(text)) return false
    if (key === 'document' || key === 'topic') {
      if (!/^[1-9][0-9]{0,15}$/.test(text) || !Number.isSafeInteger(Number(text))) return false
    }
    if (key === 'bucket' && !/^[A-Za-z0-9_:-]{1,120}$/.test(text)) return false
    if (key === 'collection' && !(collectionIds[workspace] as readonly string[]).includes(text)) return false
  }
  return true
}
function validPresets(value: unknown, workspace: 'drill' | 'ei') {
  if (!Array.isArray(value) || value.length > 10) return false
  const ids = new Set<string>()
  for (const item of value) {
    if (!record(item) || !exactKeys(item, ['id', 'name', 'query'])) return false
    if (typeof item.id !== 'string' || !/^[A-Za-z0-9_-]{1,64}$/.test(item.id) || ids.has(item.id)) return false
    if (typeof item.name !== 'string' || textLength(item.name.trim()) < 1 || textLength(item.name.trim()) > 80 || controls.test(item.name)) return false
    if (!validFilterQuery(item.query, workspace)) return false
    ids.add(item.id)
  }
  return true
}
function validGoalSettings(value: unknown): value is GoalSettings {
  if (!record(value) || !exactKeys(value, ['target', 'deadline'])
    || typeof value.target !== 'number' || !Number.isInteger(value.target) || value.target < 1 || value.target > 500
    || typeof value.deadline !== 'string' || value.deadline.length !== 10
    || !/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(value.deadline)) return false
  const [year, month, day] = value.deadline.split('-').map(Number) as [number, number, number]
  if (year < 1 || month < 1 || month > 12 || day < 1) return false
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0)
  const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
  return day <= days[month - 1]!
}
/** Validate both server snapshots and queued/offline values before they reach render. */
export function validPreference(key: string, value: unknown): boolean {
  if (own(preferenceEnums, key)) return typeof value === 'string' && preferenceEnums[key as PreferenceKey]!.includes(value)
  if (key === 'practice.review_auto_next' || key === 'practice.mastered_auto_next') return typeof value === 'boolean'
  if (key === 'sidebar.timer' || key === 'sidebar.drill' || key === 'sidebar.ei') return validSidebar(value, key.slice(8) as Workspace)
  if (key === 'filters.drill' || key === 'filters.ei') return validPresets(value, key.slice(8) as 'drill' | 'ei')
  if (key === 'progress.drill' || key === 'progress.ei') return validGoalSettings(value)
  return false
}
