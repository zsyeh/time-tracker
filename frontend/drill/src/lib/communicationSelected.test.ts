import { describe, expect, it } from 'vitest'
import { communicationFilters, communicationPracticeQuery } from './communicationSelected'

describe('communication selected context', () => {
  it('preserves priority filters and drops unrelated collection/document IDs', () => {
    expect(communicationFilters({ bucket: 'matched_filter', kind: 'calculation', combined: '1', collection: 'digital_selected', document: '15' }))
      .toEqual({ bucket: 'matched_filter', kind: 'calculation', combined: '1' })
  })
  it('keeps communication context for next and return', () => {
    expect(communicationPracticeQuery({ material: 'ready', state: 'review' }))
      .toEqual({ state: 'review', collection: 'communication_selected', from: 'communication-selected' })
  })
})
