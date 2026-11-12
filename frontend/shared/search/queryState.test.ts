import { describe, expect, it } from 'vitest'
import { clearPracticeFilters, countPracticeFilters, normalizePracticeQuery, serializePracticeQuery } from './queryState'
describe('practice query contract', () => {
  it('preserves scoped business parameters, accepts one Chinese character and rejects secrets/invalid values', () => {
    expect(normalizePracticeQuery({ collection: 'math2_selected', state: 'review', scope: 'past_exam', q: '导', page: '-3', document: 'bad', token: 'private', sort: 'source' })).toEqual({ collection: 'math2_selected', state: 'review', scope: 'past_exam', q: '导', sort: 'source' })
  })
  it('normalizes legacy filters while preserving explicit status priority', () => {
    expect(normalizePracticeQuery({ past_exam: '1', unattempted: '1' })).toEqual({ source_category: 'past_exam', status: 'unattempted' })
    expect(normalizePracticeQuery({ status: 'review', unattempted: '1' })).toEqual({ status: 'review' })
  })
  it('clears editable filters without leaving a collection scope or deleting the search', () => {
    const input = { q: '导数', collection: 'math2_selected', course: 'math', state: 'review', document: '4', topic: '8', status: 'mastered', favorite: '1', review_later: '1', sort: 'source' }
    expect(countPracticeFilters(input)).toBe(4)
    expect(clearPracticeFilters(input)).toEqual({ q: '导数', collection: 'math2_selected', course: 'math', state: 'review', sort: 'source' })
  })
  it('serializes equivalent inputs identically and omits default page/status', () => {
    expect(serializePracticeQuery({ q: ' 导数 ', page: '1', status: 'all', document: '2' })).toBe(serializePracticeQuery({ document: '2', q: '导数' }))
  })
})
