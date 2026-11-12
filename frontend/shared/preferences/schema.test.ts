import { describe, expect, it } from 'vitest'
import { preferenceDefaults, sidebarIds, validPreference, validSnapshot, type PreferenceSnapshot } from './schema'

function snapshot(): PreferenceSnapshot {
  const values = preferenceDefaults()
  return { schema_version: 1, revision: 2, values, field_revisions: Object.fromEntries(Object.keys(values).map(key => [key, 0])) }
}
const preset = (query: Record<string, unknown> = {}) => [{ id: 'saved-1', name: '导数练习', query }]

describe('account preferences boundary validation', () => {
  it('accepts complete defaults, valid revisions and safe additive future fields', () => {
    expect(validSnapshot(snapshot())).toBe(true)
    const value = { ...snapshot(), values: { ...preferenceDefaults(), 'future.safe': { mode: 'compact' } }, field_revisions: { 'future.safe': 2 } }
    expect(validSnapshot(value)).toBe(true)
  })

  it('rejects partial snapshots rather than letting sidebar render crash', () => {
    for (const key of Object.keys(preferenceDefaults())) {
      const value = snapshot()
      delete (value.values as unknown as Record<string, unknown>)[key]
      expect(validSnapshot(value), key).toBe(false)
    }
    for (const value of [null, [], {}, { ...snapshot(), values: [] }, { ...snapshot(), field_revisions: [] }, { ...snapshot(), schema_version: 2 }]) {
      expect(validSnapshot(value)).toBe(false)
    }
  })

  it('rejects unsafe revision types and bounds', () => {
    for (const revision of [-1, .5, NaN, Infinity, Number.MAX_SAFE_INTEGER + 1, true, '2']) {
      expect(validSnapshot({ ...snapshot(), revision })).toBe(false)
      expect(validSnapshot({ ...snapshot(), field_revisions: { appearance: revision } })).toBe(false)
    }
    expect(validSnapshot({ ...snapshot(), field_revisions: { appearance: 3 } })).toBe(false)
    expect(validSnapshot({ ...snapshot(), revision: Number.MAX_SAFE_INTEGER })).toBe(true)
  })

  it('validates all appearance, language and practice enums without coercion', () => {
    for (const [key, bad] of [['appearance', 'auto'], ['accent', '#fff'], ['font', '__proto__'], ['language', 'fr'], ['practice.next_mode', 'random'], ['practice.drill.copy_mode', 'clipboard'], ['practice.ei.copy_mode', 'javascript:alert(1)']]) {
      expect(validPreference(key!, bad)).toBe(false)
    }
    expect(validPreference('accent', 'monochrome')).toBe(true)
    expect(validPreference('font', 'extra-large')).toBe(true)
    expect(validPreference('practice.mastered_auto_next', false)).toBe(true)
    for (const bad of ['false', 0, 1, null]) expect(validPreference('practice.review_auto_next', bad)).toBe(false)
    expect(validPreference('runtime', {})).toBe(false)
    expect(validPreference('__proto__', {})).toBe(false)
  })

  it('validates every sidebar workspace, IDs, lists, uniqueness and transient exclusion', () => {
    for (const workspace of ['timer', 'drill', 'ei'] as const) {
      const key = `sidebar.${workspace}` as const
      const config = preferenceDefaults()[key]
      expect(validPreference(key, config)).toBe(true)
      for (const bad of [null, [], { ...config, order: null }, { ...config, hidden: 'practice' }, { ...config, order: [sidebarIds[workspace][0], sidebarIds[workspace][0]] }, { ...config, hidden: ['settings'] }, { ...config, collapsed_groups: ['drawer'] }, { ...config, collapsed_groups: ['tools', 'tools'] }, { ...config, scroll: 50 }]) {
        expect(validPreference(key, bad)).toBe(false)
      }
    }
    expect(validPreference('sidebar.drill', { order: ['core-heatmap'], hidden: [], collapsed_groups: [] })).toBe(false)
    // The server deliberately accepts subsets and appends newly introduced routes.
    expect(validPreference('sidebar.drill', { order: ['progress'], hidden: [], collapsed_groups: ['tools'] })).toBe(true)
  })

  it('accepts educational saved queries with API-aligned Unicode character lengths', () => {
    expect(validPreference('filters.drill', preset({ q: '隐函数 Fourier \\frac{x}{y}', document: '12', status: 'unattempted', collection: 'selected', marker: 'rusty', sort: 'relevance' }))).toBe(true)
    expect(validPreference('filters.ei', preset({ collection: 'core_selected', q: 'RS触发器' }))).toBe(true)
    expect(validPreference('filters.drill', preset({ q: '😀'.repeat(120) }))).toBe(true)
    expect(validPreference('filters.drill', [{ id: 'unicode', name: '😀'.repeat(80), query: {} }])).toBe(true)
  })

  it('bounds saved filters and rejects invalid, cross-workspace and transient data', () => {
    for (const bad of [null, {}, preset({ page: '2' }), preset({ index_version: 'old' }), preset({ scroll: '20' }), preset({ q: 'x'.repeat(121) }), preset({ q: '\u0000' }), preset({ document: '-1' }), preset({ topic: '9007199254740992' }), preset({ favorite: true }), preset({ status: 'invented' }), preset({ collection: 'core_selected' }), [{ ...preset()[0], id: 'bad/id' }], [{ ...preset()[0], name: '' }], [{ ...preset()[0], name: 'x'.repeat(81) }], [...preset(), ...preset()], Array.from({ length: 11 }, (_, i) => ({ id: String(i), name: 'Filter', query: {} }))]) {
      expect(validPreference('filters.drill', bad)).toBe(false)
    }
    expect(validPreference('filters.ei', preset({ collection: 'selected' }))).toBe(false)
  })

  it('rejects corrupt known cache values, polluted records and cycles', () => {
    const corrupt = snapshot()
    ;(corrupt.values as unknown as Record<string, unknown>)['sidebar.drill'] = { hidden: [] }
    expect(validSnapshot(corrupt)).toBe(false)
    const polluted = JSON.parse(JSON.stringify(snapshot()))
    polluted.values = JSON.parse('{"__proto__":{},' + JSON.stringify(polluted.values).slice(1))
    expect(validSnapshot(polluted)).toBe(false)
    expect(validSnapshot(Object.assign(Object.create({ fake: true }), snapshot()))).toBe(false)
    const cyclic = { ...snapshot(), future: null as unknown }
    cyclic.future = cyclic
    expect(validSnapshot(cyclic)).toBe(false)
  })
})
