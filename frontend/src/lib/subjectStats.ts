import type { Overview, Subject } from '../types'

export interface SubjectTimeStat {
  subject: Extract<Subject, 'math' | 'english' | 'major'>
  label: string
  minutes: number
  duration: string
  share: number
}

export function buildSubjectTimeStats(overview: Overview | null): SubjectTimeStat[] {
  const totals = new Map(overview?.subject_totals.map((item) => [item.subject, item.minutes]) || [])
  const totalMinutes = Math.max(1, overview?.summary.total_minutes || 0)
  return [
    { subject: 'math' as const, label: 'Mathematics', minutes: totals.get('math') || 0 },
    { subject: 'english' as const, label: 'English', minutes: totals.get('english') || 0 },
    { subject: 'major' as const, label: 'Major', minutes: totals.get('major') || 0 },
  ].map((item) => ({
    ...item,
    duration: `${Math.floor(item.minutes / 60)}h ${item.minutes % 60}m`,
    share: Math.round(item.minutes / totalMinutes * 100),
  }))
}
