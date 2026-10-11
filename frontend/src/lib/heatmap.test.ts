import { describe, expect, it } from 'vitest'
import { heatmapLevelClass, historicalHeatmapWindow } from './heatmap'

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

describe('timer trend windows', () => {
  it('anchors short ranges to today instead of the future exam cells', () => {
    const row = (date: string, isFuture = false) => ({
      date, is_future: isFuture, minutes: isFuture ? 0 : 60, sessions: 1,
      first_start: '08:00', level: 1 as const, five_hour_goal: false, is_exam_day: false,
    })
    const rows = [
      row('2026-10-09'), row('2026-10-10'), row('2026-10-11'), row('2026-10-12'),
      row('2026-10-13', true), row('2026-12-26', true),
    ]

    expect(historicalHeatmapWindow(rows, '2026-10-12', 3).map((item) => item.date)).toEqual([
      '2026-10-10', '2026-10-11', '2026-10-12',
    ])
  })
})
