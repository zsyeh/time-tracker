import { describe, expect, it } from 'vitest'
import { circuitFilters, circuitPracticeQuery } from './circuitSelected'

describe('circuit collection navigation', () => {
  it('preserves the same filters when opening and returning from a question', () => {
    const q = { bucket: 'first_order', tier: 'core', material: 'ready', state: 'review', combined: '1', kind: 'calculation' }
    const next = circuitPracticeQuery(q)
    expect(next).toMatchObject({ ...q, from: 'circuit-selected', collection: 'circuit_selected' })
    expect(circuitFilters(next)).toEqual(q)
  })
  it('does not carry unrelated book/category/history queries into the collection', () => {
    expect(circuitFilters({ document: '25', topic: '1', from: 'heatmap', tier: '', state: ['review'] })).toEqual({})
  })
})
