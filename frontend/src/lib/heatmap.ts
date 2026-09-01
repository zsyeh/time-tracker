import type { HeatmapDay } from '../types'

const EIGHT_HOURS = 8 * 60
const TEN_HOURS = 10 * 60
const TWELVE_HOURS = 12 * 60

export function heatmapLevelClass(day: Pick<HeatmapDay, 'minutes' | 'level'>) {
  if (day.minutes > TWELVE_HOURS) return 'level-12-plus'
  if (day.minutes > TEN_HOURS) return 'level-10-plus'
  if (day.minutes > EIGHT_HOURS) return 'level-8-plus'
  return `level-${day.level}`
}
