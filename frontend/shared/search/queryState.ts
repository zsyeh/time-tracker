/** Public query keys only. User content and secrets must never enter list URLs. */
export const practiceScopeKeys = ['collection', 'bucket', 'tier', 'kind', 'combined', 'state', 'material', 'course', 'scope', 'from'] as const
export const practiceFilterKeys = ['document', 'topic', 'source_category', 'type_group', 'exam_type', 'status', 'favorite', 'review_later', 'marker', 'include_structure'] as const
export const practiceStatuses = ['all', 'unattempted', 'mastered', 'review', 'overdue'] as const
export type PracticeStatus = typeof practiceStatuses[number]
export type PracticeQuery = Record<string, string>
const allowed = new Set<string>([...practiceScopeKeys, ...practiceFilterKeys, 'q', 'page', 'sort', 'search_version', 'index_version'])

export function normalizePracticeQuery(input: Record<string, unknown>): PracticeQuery {
  const output: PracticeQuery = {}
  for (const [key, raw] of Object.entries(input)) {
    if (!allowed.has(key) || Array.isArray(raw) || raw === null || raw === undefined) continue
    const value = String(raw).trim()
    if (value) output[key] = value
  }
  if (!output.source_category && input.past_exam === '1') output.source_category = 'past_exam'
  if (!output.status && input.unattempted === '1') output.status = 'unattempted'
  if (!practiceStatuses.includes(output.status as PracticeStatus) || output.status === 'all') delete output.status
  if (!['relevance', 'source'].includes(output.sort || '')) delete output.sort
  if (!output.q && output.sort === 'relevance') delete output.sort
  for (const key of ['document', 'topic']) if (output[key] && !/^[1-9]\d*$/.test(output[key])) delete output[key]
  const page = Number(output.page)
  if (!Number.isSafeInteger(page) || page <= 1) { delete output.page; delete output.index_version }
  if (output.search_version !== '2') delete output.search_version
  for (const key of ['favorite', 'review_later', 'include_structure']) if (output[key] !== '1') delete output[key]
  return output
}
export function serializePracticeQuery(input: Record<string, unknown>) {
  const normalized = normalizePracticeQuery(input)
  return new URLSearchParams(Object.entries(normalized).sort(([a], [b]) => a.localeCompare(b))).toString()
}
export function clearPracticeFilters(input: PracticeQuery): PracticeQuery {
  return normalizePracticeQuery(Object.fromEntries(Object.entries(input).filter(([key]) => !practiceFilterKeys.includes(key as typeof practiceFilterKeys[number]))))
}
export function countPracticeFilters(input: PracticeQuery) {
  // Document+topic are one semantic group; the type family is also one group.
  return Number(Boolean(input.document || input.topic)) + Number(Boolean(input.type_group || input.exam_type))
    + ['source_category', 'status', 'favorite', 'review_later', 'marker', 'include_structure'].filter((key) => Boolean(input[key])).length
}
