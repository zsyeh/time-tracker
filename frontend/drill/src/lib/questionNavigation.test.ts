import { describe, expect, it } from 'vitest'
import { emptyNextQuestionMessage, nextQuestionTarget } from './questionNavigation'

const question = {
  sequential_next_question_uuid: 'sequential-uuid',
  next_overdue_review_uuid: 'overdue-uuid',
  next_review_uuid: 'review-uuid',
}

describe('question navigation modes', () => {
  it.each([
    ['sequential', 'sequential-uuid'],
    ['overdue', 'overdue-uuid'],
    ['review', 'review-uuid'],
  ] as const)('selects the %s target without another request', (mode, expected) => {
    expect(nextQuestionTarget(question, mode)).toBe(expected)
  })

  it('returns a specific recoverable empty-state message for every mode', () => {
    expect(emptyNextQuestionMessage('sequential')).toContain('下一题')
    expect(emptyNextQuestionMessage('overdue')).toContain('红色')
    expect(emptyNextQuestionMessage('review')).toContain('黄色')
  })
})
