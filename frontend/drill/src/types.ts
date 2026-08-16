export interface QuestionSummary {
  uuid: string
  document: string
  question_order: number
  source_label: string
  topic: string
  is_past_exam: boolean
  exam_year: number | null
  exam_variant: string
  attempt_count: number
  latest_result: 'done' | 'correct' | 'review' | null
}

export interface QuestionDetail extends QuestionSummary {
  prompt_text: string
  latex_text: string
  content_mode: string
  breadcrumbs: Array<{ id: number; title: string; level: number }>
  assets: Array<{ id: number; url: string; width: number; height: number; position: number }>
}

export interface Catalog {
  documents: Array<{
    id: number
    title: string
    question_count: number
    past_exam_count: number
    attempted_count: number
  }>
  topics: Array<{
    id: number
    document_id: number
    title: string
    question_count: number
  }>
}

export interface Page<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export interface Progress {
  total_attempts: number
  attempted_questions: number
  correct_attempts: number
  review_attempts: number
  past_exam_questions: number
  question_count: number
  past_exam_count: number
}

