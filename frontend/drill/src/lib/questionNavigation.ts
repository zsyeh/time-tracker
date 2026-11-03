import type { QuestionDetail } from '../types'

export type NextQuestionMode = 'sequential' | 'overdue' | 'review'

type NavigationQuestion = Pick<
  QuestionDetail,
  'sequential_next_question_uuid' | 'next_overdue_review_uuid' | 'next_review_uuid'
>

export function nextQuestionTarget(question: NavigationQuestion, mode: NextQuestionMode) {
  if (mode === 'overdue') return question.next_overdue_review_uuid
  if (mode === 'review') return question.next_review_uuid
  return question.sequential_next_question_uuid
}

export function emptyNextQuestionMessage(mode: NextQuestionMode) {
  if (mode === 'overdue') return '没有剩余的红色到期复习题。'
  if (mode === 'review') return '没有剩余的黄色近期复习题。'
  return '当前题源中没有下一题。'
}
