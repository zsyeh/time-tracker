export type Subject = 'math' | 'english' | 'major' | 'training'

export interface StudySession {
  id: number
  subject: Subject
  subject_label: string
  chapter: string
  topic: string
  start_time: string
  end_time: string | null
  duration_minutes: number
  status: 'running' | 'completed' | 'abandoned'
  learning_mode: string
  difficulty: number | null
  energy_level: string
  focus_level: number | null
  confidence_before: number | null
  confidence_after: number | null
  title: string
  details: string
  breakthrough: string
  problems: string
  next_action: string
}

export interface HeatmapDay {
  date: string
  minutes: number
  sessions: number
  first_start: string | null
  level: 0 | 1 | 2 | 4
  five_hour_goal: boolean
}

export interface Overview {
  server_time: string
  range_days: number
  calendar: { today: string; exam_date: string; days_until_exam: number; heatmap_start_date: string }
  today: { minutes: number; sessions: number; first_start: string | null }
  active_session: StudySession | null
  summary: {
    total_minutes: number
    session_count: number
    active_days: number
    five_hour_days: number
    current_streak: number
    longest_streak: number
    current_five_hour_streak: number
    longest_five_hour_streak: number
    average_start_time: string | null
  }
  subject_totals: Array<{ subject: Subject; minutes: number }>
  today_subject_totals: Array<{ subject: Subject; minutes: number }>
  weekly_totals: Array<{ week_start: string; minutes: number }>
  monthly_totals: Array<{ month: string; minutes: number }>
  heatmap: HeatmapDay[]
  daily_start_times: Array<{ date: string; first_start: string }>
}

export interface Issue {
  id: number
  subject: Subject
  topic: string
  study_session: number | null
  issue_type: string
  description: string
  solution: string
  resolved: boolean
  repeat_count: number
  created_at: string
}

export interface KnowledgePoint {
  id: number
  subject: Subject
  name: string
  parent: number | null
  importance: number
  mastery_score: number
  status: string
  last_reviewed_at: string | null
  review_count: number
}

export interface LaunchToken {
  id: number
  name: string
  subject: Subject
  is_active: boolean
  expires_at: string | null
  max_uses: number | null
  usage_count: number
  source_label: string
  usable: boolean
  raw_token?: string
  launch_url?: string
}

export interface Page<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export interface GlobalSearchResult {
  kind: 'session' | 'issue'
  record_id: number
  title: string
  snippet: string
  subject: Subject
  subject_label: string
  occurred_at: string
}

export interface GlobalSearchResponse {
  query: string
  results: GlobalSearchResult[]
}
