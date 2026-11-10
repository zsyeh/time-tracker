import type { NextQuestionMode } from './questionNavigation'
export type ReaderPracticeAction = 'previous' | 'next' | 'mastered' | 'review' | 'answer'
export interface ReaderPracticeControls {
  mode: NextQuestionMode
  canPrevious: boolean
  canNext: boolean
  answerActive?: boolean
  canAnswer: boolean
  busy: boolean
  masteredAutoNext: boolean
  reviewAutoNext: boolean
  state: string
  error: string
  feedback: string
}
export function readerDestinationColour(mode: NextQuestionMode, base: string) {
  return mode === 'overdue' ? 'var(--danger, #e37179)' : mode === 'review' ? 'var(--warning, #d4a857)' : base
}
