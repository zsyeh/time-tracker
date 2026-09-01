import { describe, expect, it } from 'vitest'
import { heatmapLevelClass } from './heatmap'

describe('timer heatmap milestone colors', () => {
  it.each([
    [300, 'level-4'],
    [480, 'level-4'],
    [481, 'level-8-plus'],
    [600, 'level-8-plus'],
    [601, 'level-10-plus'],
    [720, 'level-10-plus'],
    [721, 'level-12-plus'],
  ])('maps %i minutes to %s', (minutes, expected) => {
    expect(heatmapLevelClass({ minutes, level: 4 })).toBe(expected)
  })

  it('preserves the existing lower activity level', () => {
    expect(heatmapLevelClass({ minutes: 119, level: 1 })).toBe('level-1')
  })
})
