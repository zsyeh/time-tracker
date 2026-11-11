import type { QuestionDetail } from '../types'

export type NextQuestionMode = 'sequential' | 'overdue' | 'review' | 'unattempted'

type NextNavigationQuestion = Pick<
  QuestionDetail,
  'sequential_next_question_uuid' | 'next_overdue_review_uuid' | 'next_review_uuid' | 'next_unattempted_question_uuid'
>

type PreviousNavigationQuestion = Pick<
  QuestionDetail,
  'previous_question_uuid' | 'previous_overdue_review_uuid' | 'previous_review_uuid' | 'previous_unattempted_question_uuid'
>

export function nextQuestionTarget(question: NextNavigationQuestion, mode: NextQuestionMode) {
  if (mode === 'unattempted') return question.next_unattempted_question_uuid ?? null
  if (mode === 'overdue') return question.next_overdue_review_uuid
  if (mode === 'review') return question.next_review_uuid
  return question.sequential_next_question_uuid
}

export function previousQuestionTarget(question: PreviousNavigationQuestion, mode: NextQuestionMode) {
  if (mode === 'unattempted') return question.previous_unattempted_question_uuid ?? null
  if (mode === 'overdue') return question.previous_overdue_review_uuid
  if (mode === 'review') return question.previous_review_uuid
  return question.previous_question_uuid
}

export function emptyNextQuestionMessage(mode: NextQuestionMode) {
  if (mode === 'unattempted') return '当前筛选范围中没有其他未做题。'
  if (mode === 'overdue') return '没有剩余的红色到期复习题。'
  if (mode === 'review') return '没有剩余的黄色近期复习题。'
  return '当前题源中没有下一题。'
}

export function emptyPreviousQuestionMessage(mode: NextQuestionMode) {
  if (mode === 'unattempted') return '当前筛选范围中没有其他未做题。'
  if (mode === 'overdue') return '没有剩余的红色到期复习题。'
  if (mode === 'review') return '没有剩余的黄色近期复习题。'
  return '当前筛选范围中没有上一题。'
}
