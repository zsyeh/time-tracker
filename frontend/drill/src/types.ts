export interface QuestionSummary {
  uuid: string
  document: string
  question_order: number
  source_label: string
  display_label: string
  topic: string
  is_past_exam: boolean
  source_category: 'past_exam' | 'adapted_exam' | 'mock_exam' | 'workbook' | 'competition' | 'other_practice' | 'unclassified'
  source_category_label: string
  record_kind: 'question' | 'grouped' | 'section'
  exam_year: number | null
  exam_variant: string
  attempt_count: number
  latest_result: 'done' | 'correct' | 'review' | 'reset' | null
  state: 'unattempted' | 'mastered' | 'review'
  can_undo: boolean
  is_favorite: boolean
  review_later: boolean
  saved_note: string
  confidence?: number | null
  note?: string | null
}

export interface QuestionDetail extends QuestionSummary {
  prompt_text: string
  latex_text: string
  content_mode: string
  formula_source: 'tex' | 'original_pdf_crop'
  document_author: string
  document_attribution: string
  previous_question_uuid: string | null
  next_question_uuid: string | null
  confidence: number | null
  note: string | null
  markers: QuestionMarkerCode[]
  breadcrumbs: Array<{ id: number; title: string; level: number }>
  assets?: Array<{ id: number; url: string; width: number; height: number; position: number }>
  question_assets?: Array<{ id: number; url: string; width: number; height: number; position: number }>
  answer_assets: Array<{ id: number; url: string; width: number; height: number; position: number }>
  has_answer: boolean
  answer_markdown: string
  answer_source: string
  answer_confidence: number | null
  answer_generated_at: string | null
}

export type QuestionMarkerCode = 'overconfident' | 'concept_gap' | 'rusty' | 'forgotten'

export interface Catalog {
  summary: {
    imported_count: number
    practiceable_count: number
    outline_count: number
    categories: Array<{ value: QuestionSummary['source_category']; label: string; count: number }>
  }
  coverage: {
    available: string[]
    missing: string[]
    source_archive_checked: boolean
  }
  documents: Array<{
    id: number
    title: string
    author: string
    attribution: string
    question_count: number
    imported_count: number
    past_exam_count: number
    attempted_count: number
  }>
  topics: Array<{
    id: number
    document_id: number
    title: string
    path: string
    level: number
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

export interface CollectionPayload {
  kind: 'favorite' | 'review_later'
  count: number
  next: string | null
  previous: string | null
  results: QuestionSummary[]
}

export interface BookFeel {
  document_id: number
  document: string
  question_count: number
  last_practiced_at: string | null
  days_idle: number | null
  feel_score: number | null
  recent_attempts: number
}

export interface InsightPayload {
  marker_stats: Array<{
    code: QuestionMarkerCode
    label: string
    count: number
  }>
  recent_questions: Array<{
    uuid: string
    label: string
    document: string
    topic: string
    result: 'done' | 'correct' | 'review'
    created_at: string
  }>
  recent_notes: Array<{
    uuid: string
    label: string
    document: string
    topic: string
    note: string
    updated_at: string
  }>
}
