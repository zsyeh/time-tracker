import type { QuestionDetail } from '../types'

// Old paper bookmarks should lead to actual practice once ALL indexed items
// have individual crops. Explicit original-view links must remain accessible.
export function sourcePracticeTarget(question: Pick<QuestionDetail, 'source_context'>, view: unknown) {
  const context = question.source_context
  if (view === 'original' || !context?.prefer_individual_practice || context.anchor || !context.index_complete || !context.anchors.length) return null
  if (!context.anchors.every((item) => item.individual_available)) return null
  return context.anchors[0].uuid
}
