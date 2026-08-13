import { describe, expect, it } from 'vitest'
import { buildSubjectTimeStats } from './subjectStats'
import type { Overview } from '../types'

describe('buildSubjectTimeStats', () => {
  it('returns the three tracked subjects with readable totals and total-share percentages', () => {
    const overview = {
      subject_totals: [
        { subject: 'math', minutes: 125 },
        { subject: 'english', minutes: 60 },
      ],
      summary: { total_minutes: 200 },
    } as Overview

    expect(buildSubjectTimeStats(overview)).toEqual([
      { subject: 'math', label: 'Mathematics', minutes: 125, duration: '2h 5m', share: 63 },
      { subject: 'english', label: 'English', minutes: 60, duration: '1h 0m', share: 30 },
      { subject: 'major', label: 'Major', minutes: 0, duration: '0h 0m', share: 0 },
    ])
  })
})
