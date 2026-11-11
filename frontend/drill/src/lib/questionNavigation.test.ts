import { describe, expect, it } from 'vitest'
import { emptyNextQuestionMessage, emptyPreviousQuestionMessage, nextQuestionTarget, previousQuestionTarget } from './questionNavigation'

const question = {
  sequential_next_question_uuid: 'sequential-uuid',
  next_overdue_review_uuid: 'overdue-uuid',
  next_review_uuid: 'review-uuid',
  next_unattempted_question_uuid: 'unattempted-uuid',
  previous_question_uuid: 'previous-sequential-uuid',
  previous_overdue_review_uuid: 'previous-overdue-uuid',
  previous_review_uuid: 'previous-review-uuid',
  previous_unattempted_question_uuid: 'previous-unattempted-uuid',
}

describe('question navigation modes', () => {
  it.each([
    ['sequential', 'sequential-uuid'],
    ['overdue', 'overdue-uuid'],
    ['review', 'review-uuid'],
    ['unattempted', 'unattempted-uuid'],
  ] as const)('selects the %s target without another request', (mode, expected) => {
    expect(nextQuestionTarget(question, mode)).toBe(expected)
  })

  it.each([
    ['sequential', 'previous-sequential-uuid'],
    ['overdue', 'previous-overdue-uuid'],
    ['review', 'previous-review-uuid'],
    ['unattempted', 'previous-unattempted-uuid'],
  ] as const)('selects the previous %s target with the same mode', (mode, expected) => {
    expect(previousQuestionTarget(question, mode)).toBe(expected)
  })

  it('never falls back to sequential when an unattempted destination is missing', () => {
    const exhausted = { ...question, next_unattempted_question_uuid: null, previous_unattempted_question_uuid: null }
    expect(nextQuestionTarget(exhausted, 'unattempted')).toBeNull()
    expect(previousQuestionTarget(exhausted, 'unattempted')).toBeNull()
    expect(nextQuestionTarget({ ...question, next_unattempted_question_uuid: undefined }, 'unattempted')).toBeNull()
  })

  it('returns a specific recoverable empty-state message for every mode', () => {
    expect(emptyNextQuestionMessage('sequential')).toContain('下一题')
    expect(emptyNextQuestionMessage('overdue')).toContain('红色')
    expect(emptyNextQuestionMessage('review')).toContain('黄色')
    expect(emptyPreviousQuestionMessage('sequential')).toContain('上一题')
    expect(emptyPreviousQuestionMessage('overdue')).toContain('红色')
    expect(emptyPreviousQuestionMessage('review')).toContain('黄色')
    expect(emptyNextQuestionMessage('unattempted')).toContain('没有其他未做题')
    expect(emptyPreviousQuestionMessage('unattempted')).toContain('没有其他未做题')
  })
})
