import { describe, expect, it } from 'vitest'
import { digitalFilters, digitalPracticeQuery } from './digitalSelected'

describe('digital selected context', () => {
  it('retains analysis/design filters without leaking other collection IDs', () => {
    expect(digitalFilters({ bucket: 'sync_design', kind: 'design', tier: 'advanced', collection: 'analog_selected', document: '13' }))
      .toEqual({ bucket: 'sync_design', kind: 'design', tier: 'advanced' })
  })
  it('preserves standard-template filtering and return origin', () => {
    expect(digitalPracticeQuery({ combined: '1', material: 'ready' }))
      .toEqual({ combined: '1', collection: 'digital_selected', from: 'digital-selected' })
  })
})
