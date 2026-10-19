import { describe, expect, it } from 'vitest'
import { heatmapProgress } from './heatmapProgress'

describe('heatmap question progress', () => {
  it('uses different denominators for attempted and total mastery', () => {
    expect(heatmapProgress(100, 25, 10)).toEqual({
      attempted: 25, unattempted: 75, mastered: 10,
      attemptedMasterRate: '40%', totalMasterRate: '10%',
    })
  })
  it('keeps an unstarted nonempty book at zero total mastery', () => {
    expect(heatmapProgress(355, 0, 0)).toMatchObject({
      unattempted: 355, attemptedMasterRate: '—', totalMasterRate: '0%',
    })
  })
  it('does not divide by zero for an empty filter', () => {
    expect(heatmapProgress(0, 0, 0)).toMatchObject({
      unattempted: 0, attemptedMasterRate: '—', totalMasterRate: '—',
    })
  })
  it('rounds fractional rates to one decimal place', () => {
    expect(heatmapProgress(9, 3, 2)).toMatchObject({
      attemptedMasterRate: '66.7%', totalMasterRate: '22.2%',
    })
  })
  it('handles a fully mastered book', () => {
    expect(heatmapProgress(12, 12, 12)).toMatchObject({
      unattempted: 0, attemptedMasterRate: '100%', totalMasterRate: '100%',
    })
  })
})
