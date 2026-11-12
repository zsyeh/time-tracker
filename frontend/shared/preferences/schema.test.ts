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

  it('preserves progress defaults independently per workspace and snapshot', () => {
    const first = preferenceDefaults()
    expect(first['progress.drill']).toEqual({ target: 24, deadline: '2026-11-21' })
    expect(first['progress.ei']).toEqual({ target: 11, deadline: '2026-11-21' })
    first['progress.drill'].target = 40
    expect(first['progress.ei'].target).toBe(11)
    expect(preferenceDefaults()['progress.drill'].target).toBe(24)
    expect(validSnapshot(snapshot())).toBe(true)
  })

  it('accepts integer workload limits and valid calendar dates without timezone coercion', () => {
    for (const key of ['progress.drill', 'progress.ei']) {
      for (const target of [1, 11, 24, 500]) {
        for (const deadline of ['0001-01-01', '2000-02-29', '2024-02-29', '2026-02-28', '9999-12-31']) {
          expect(validPreference(key, { target, deadline }), `${key} ${target} ${deadline}`).toBe(true)
        }
      }
    }
    expect(validPreference('progress.timer', { target: 24, deadline: '2026-11-21' })).toBe(false)
  })

  it('rejects malformed goals, impossible dates and arbitrary progress logic fields', () => {
    const goal = { target: 24, deadline: '2026-11-21' }
    const invalid: unknown[] = [null, [], {}, { target: 24 }, { deadline: goal.deadline }, { ...goal, total: 963 }, { ...goal, formula: 'override' }]
    invalid.push(...[0, -1, 501, true, false, 1.5, '24', null, NaN, Infinity].map(target => ({ ...goal, target })))
    invalid.push(...[null, 20261121, '', '2026-2-01', '2026-02-29', '1900-02-29', '2026-04-31', '2026-00-01', '2026-13-01', '2026-01-00', '0000-01-01', '10000-01-01', '2026-11-21T00:00:00Z', '2026-11-21\n', ' 2026-11-21', '２０２６-１１-２１'].map(deadline => ({ ...goal, deadline })))
    for (const key of ['progress.drill', 'progress.ei']) {
      for (const value of invalid) expect(validPreference(key, value), JSON.stringify(value)).toBe(false)
    }
    const corrupt = snapshot()
    corrupt.values['progress.ei'].deadline = '2026-02-29'
    expect(validSnapshot(corrupt)).toBe(false)
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

it('validates finite custom copy scales without coercing booleans or strings',()=>{
 for(const n of [1,2,3,4,1.5,8])expect(validPreference('practice.image_copy_scale',n)).toBe(true)
 for(const bad of [true,'2',0,-1,8.1,NaN,Infinity,null])expect(validPreference('practice.image_copy_scale',bad)).toBe(false)
})
