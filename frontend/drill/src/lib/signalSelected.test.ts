import { describe, expect, it } from 'vitest'
import { signalFilters, signalPracticeQuery } from './signalSelected'

describe('signal selected navigation', () => {
  it('retains only supported filters and never an old circuit collection', () => {
    expect(signalFilters({ bucket: 'fourier', kind: 'calculation', state: 'review', document: '14', collection: 'circuit_selected', topic: ['1', '2'] }))
      .toEqual({ bucket: 'fourier', kind: 'calculation', state: 'review' })
  })
  it('keeps signal return context and initial-condition filter', () => {
    expect(signalPracticeQuery({ tier: 'core', combined: '1', material: 'ready' }))
      .toEqual({ tier: 'core', combined: '1', material: 'ready', collection: 'signal_selected', from: 'signal-selected' })
  })
})
