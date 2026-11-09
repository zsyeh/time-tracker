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
  review_overdue: boolean
  pdf_pages: { course: string; question: number; answer: number; paired: number } | null
  confidence?: number | null
  note?: string | null
  state_version?: number
}

export interface QuestionDetail extends QuestionSummary {
  original_source?: { uuid: string; label: string; has_answer?: boolean }
  answer_scope?: 'source_paper' | 'individual'
  source_review_warning?: string
  source_context?: {
    source_uuid: string
    source_label: string
    answer_scope: 'source_paper' | 'individual'
    index_complete?: boolean
    individual_question_count?: number
    prefer_individual_practice?: boolean
    anchor: { asset_id: number; y: number } | null
    anchors: Array<{ uuid: string; label: string; asset_id: number; y: number; position: number; state: 'unattempted' | 'mastered' | 'review'; individual_available?: boolean }>
  }
  prompt_text: string
  latex_text: string
  content_mode: string
  formula_source: 'tex' | 'original_pdf_crop'
  document_author: string
  document_attribution: string
  previous_question_uuid: string | null
  previous_overdue_review_uuid: string | null
  previous_review_uuid: string | null
  next_question_uuid: string | null
  sequential_next_question_uuid: string | null
  next_overdue_review_uuid: string | null
  next_review_uuid: string | null
  confidence: number | null
  last_time_spent_seconds: number | null
  last_timed_at: string | null
  note: string | null
  state_version: number
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
  latest_diagnosis: AttemptDiagnosis | null
  review_plan: ReviewPlan | null
}

export type ErrorCode = 'A' | 'B1' | 'B2' | 'B3' | 'C1' | 'C2' | 'C3' | 'D'

export interface AttemptDiagnosis {
  id: number
  result: 'done' | 'correct' | 'review' | 'reset'
  outcome: 'unknown' | 'correct' | 'incorrect' | 'incomplete'
  knowledge_level: 'K0' | 'K1' | 'K2' | null
  method_level: 'M0' | 'M1' | 'M2' | null
  execution_level: 'E0' | 'E1' | 'E2' | null
  used_hint: boolean | null
  viewed_answer: boolean | null
  is_independent: boolean | null
  judgement_source: 'unknown' | 'self' | 'auto'
  training_stage: 'unknown' | 'first' | 'same_day_redo' | 'next_day_redo' | 'review'
  attempt_round: number | null
  correction_note: string
  knowledge_note: string
  first_step_note: string
  time_spent_seconds: number | null
  started_at: string | null
  created_at: string
  errors: Array<{ code: ErrorCode; is_primary: boolean }>
  primary_error: ErrorCode | null
}

export interface ReviewPlan {
  status: 'active' | 'completed' | 'paused'
  step: number
  checkpoint: string
  schedule_days: number[]
  next_review_at: string | null
}

export interface DiagnosticMetric {
  value: number | null
  numerator?: number
  sample: number
}

export interface DiagnosticDashboard {
  workspace: 'drill' | 'ei'
  range: { start: string; end: string }
  today: { new_questions: number; review_questions: number; completed_questions: number; submissions: number; first_sample: number; first_independent_correct: number }
  period_activity: { daily_unique_questions: number; submissions: number; unique_questions: number; diagnosed_attempts: number; legacy_unknown_attempts: number }
  activity: Array<{ date: string; daily_unique_questions: number; submissions: number; new_questions: number; review_questions: number; diagnosed_questions: number; legacy_unknown_questions: number }>
  metrics: {
    first_independent_accuracy: DiagnosticMetric
    second_independent_accuracy: DiagnosticMetric
    pending_redo_count: number
    error_recurrence_rate: DiagnosticMetric
    method_start_failure_rate: DiagnosticMetric
  }
  error_distribution: Array<{ code: ErrorCode; count: number }>
  due_count: number
  trend: Array<{
    date: string
    first_sample: number
    first_independent_correct: number
    second_sample: number
    second_independent_correct: number
  }>
  courses: Array<{
    code: string
    label: string
    question_count: number
    first_sample: number
    first_independent_accuracy: number | null
    knowledge_gap_rate: number | null
    method_failure_rate: number | null
    execution_error_rate: number | null
    redo_sample: number
    redo_pass_rate: number | null
  }>
  repeated_topics: Array<{ topic: string; diagnosed_errors: number }>
  topic_trends: Array<{ topic: string; current_rate: number; previous_rate: number; change: number; current_sample: number; previous_sample: number }>
  notice: string
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

export interface ActivityDay {
  date: string
  count: number
  level: number
  is_future: boolean
}

export interface ActivityCalendarData {
  total_attempts: number
  active_days: number
  max_daily_count: number
  days: ActivityDay[]
}

export interface ActivityPayload {
  start_date: string
  end_date: string
  today: string
  overall: ActivityCalendarData
  books: Array<ActivityCalendarData & { document_id: number; document: string }>
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
  recent_questions: InsightPage<{
    uuid: string
    label: string
    document: string
    topic: string
    result: 'done' | 'correct' | 'review'
    created_at: string
    diagnoses: ErrorCode[]
  }>
  recent_notes: InsightPage<{
    uuid: string
    label: string
    document: string
    topic: string
    note: string
    updated_at: string
    result: 'done' | 'correct' | 'review' | null
    primary_error: ErrorCode | null
  }>
  options: {
    errors: Array<{ code: ErrorCode; label: string }>
    courses: Array<{ code: string; label: string }>
    documents: Array<{ id: number; label: string }>
    topics: Array<{ id: number; label: string }>
  }
}

export interface InsightPage<T> {
  count: number
  page: number
  page_size: number
  total_pages: number
  next_page: number | null
  previous_page: number | null
  results: T[]
}

export type PaperMode = 'standard' | 'intensive' | 'weak'
export type PaperStatus = 'generated' | 'in_progress' | 'completed'
export type PaperItemResult = 'unanswered' | 'correct' | 'incorrect' | 'review'

export interface ExamBlueprintSection {
  title: string
  question_type: 'single_choice' | 'fill_blank' | 'solution'
  question_count: number
  score_per_question: number
}

export interface ExamBlueprint {
  uuid: string
  code: string
  title: string
  mode: PaperMode
  version: number
  duration_minutes: number
  total_score: number
  cooldown_days: number
  question_count: number
  sections: ExamBlueprintSection[]
}

export interface ExamPaperQuestion {
  uuid: string
  display_label: string
  source_label: string
  document: string
  topic: string
  question_type: 'single_choice' | 'fill_blank' | 'solution'
  prompt_text: string
  latex_text: string
  content_mode: string
  question_assets: Array<{ id: number; url: string; width: number; height: number; position: number }>
  answer_markdown?: string
  answer_source?: string
  answer_assets?: Array<{ id: number; url: string; width: number; height: number; position: number }>
  mastery_state?: 'unattempted' | 'mastered' | 'review'
}

export interface ExamPaperItem {
  position: number
  score: number
  user_answer: string
  result: PaperItemResult
  time_spent_seconds: number | null
  question: ExamPaperQuestion
}

export interface ExamPaper {
  uuid: string
  title: string
  blueprint: string
  mode: PaperMode
  status: PaperStatus
  seed: number
  duration_minutes: number
  total_score: number
  created_at: string
  started_at: string | null
  completed_at: string | null
  items: ExamPaperItem[]
}

export interface ExamPaperSummary {
  uuid: string
  title: string
  blueprint: string
  mode: PaperMode
  status: PaperStatus
  created_at: string
  completed_at: string | null
  duration_minutes: number
  total_score: number
  question_count: number
  answered_count: number
  correct_count: number
  time_spent_seconds: number
  earned_score: number
}
