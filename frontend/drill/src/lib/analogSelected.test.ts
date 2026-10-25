import { describe, expect, it } from 'vitest'
import { analogFilters, analogPracticeQuery } from './analogSelected'

describe('analog selected context', () => {
  it('preserves filters but drops unrelated collections', () => {
    expect(analogFilters({ bucket: 'feedback', tier: 'core', state: 'review', collection: 'signal_selected', document: '12' }))
      .toEqual({ bucket: 'feedback', tier: 'core', state: 'review' })
  })
  it('keeps the analog origin and static/dynamic combination', () => {
    expect(analogPracticeQuery({ combined: '1', material: 'ready' }))
      .toEqual({ combined: '1', material: 'ready', collection: 'analog_selected', from: 'analog-selected' })
  })
})
