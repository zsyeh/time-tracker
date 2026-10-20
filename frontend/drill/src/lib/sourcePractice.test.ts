import { describe, expect, it } from 'vitest'
import type { QuestionDetail } from '../types'
import { sourcePracticeTarget } from './sourcePractice'

function paper() {
  return { source_context: { source_uuid: 'paper', source_label: '2018', answer_scope: 'source_paper',
    index_complete: true, prefer_individual_practice: true, anchor: null, anchors: [
      { uuid: 'first', label: '1', asset_id: 1, y: .2, position: 1, state: 'unattempted', individual_available: true },
      { uuid: 'second', label: '2', asset_id: 1, y: .5, position: 2, state: 'unattempted', individual_available: true },
    ] } } as Pick<QuestionDetail, 'source_context'>
}

describe('source paper practice entry', () => {
  it('opens the first individual question for an archived complete paper', () => {
    expect(sourcePracticeTarget(paper(), undefined)).toBe('first')
  })
  it('keeps the full original available with its explicit link', () => {
    expect(sourcePracticeTarget(paper(), 'original')).toBeNull()
  })
  it('does not redirect an incomplete paper or partially cropped source', () => {
    const value = paper(); value.source_context!.index_complete = false
    expect(sourcePracticeTarget(value, undefined)).toBeNull()
    value.source_context!.index_complete = true
    value.source_context!.anchors[1].individual_available = false
    expect(sourcePracticeTarget(value, undefined)).toBeNull()
  })
  it('does not redirect independently tracked questions or old cached payloads', () => {
    const value = paper(); value.source_context!.anchor = { asset_id: 1, y: .2 }
    expect(sourcePracticeTarget(value, undefined)).toBeNull()
    value.source_context!.anchor = null
    delete value.source_context!.anchors[0].individual_available
    expect(sourcePracticeTarget(value, undefined)).toBeNull()
    expect(sourcePracticeTarget({}, undefined)).toBeNull()
  })
  it('does not change original-page navigation outside the EI opt-in', () => {
    const value = paper(); value.source_context!.prefer_individual_practice = false
    expect(sourcePracticeTarget(value, undefined)).toBeNull()
  })
})
