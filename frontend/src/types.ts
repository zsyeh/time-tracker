export type Subject = 'math' | 'english' | 'major' | 'training'
export type EfficiencyGrade = 'A' | 'B' | 'C' | 'D' | 'E' | 'F'

export interface StudyTag {
  id: number
  name: string
  color: string
  created_at?: string
}

export interface TaskPreset {
  id: number
  uuid: string
  subject: Subject
  subject_label: string
  name: string
  parent: number | null
  depth: number
  path: string
  shortcut_label: string
  tags: StudyTag[]
  is_home_shortcut: boolean
  is_active: boolean
  sort_order: number
  created_at: string
  updated_at: string
}

export interface TaskShortcut {
  id: number
  subject: Subject
  subject_label: string
  name: string
  path: string
  label: string
  tags: StudyTag[]
}

export interface CompletionOptions {
  presets: TaskPreset[]
  tags: StudyTag[]
  recent_titles: string[]
}

export interface StudySessionSummary {
  id: number
  uuid: string
  subject: Subject
  subject_label: string
  start_time: string
  end_time: string | null
  duration_minutes: number
  efficiency_grade: EfficiencyGrade
  efficiency_coefficient: number
  credited_duration_minutes: number
  status: 'running' | 'completed' | 'abandoned'
  title: string | null
  task_preset: number | null
  task_path: string
  tags: StudyTag[]
  review_count: number
  last_reviewed_at: string | null
}

export interface StudySession extends StudySessionSummary {
  chapter: string
  topic: string
  learning_mode: string
  difficulty: number | null
  energy_level: string
  focus_level: number | null
  confidence_before: number | null
  confidence_after: number | null
  details: string
  breakthrough: string
  problems: string
  next_action: string
  disturbance_count: number
  last_disturbance_at: string | null
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
  features: { math_visualization: boolean }
  calendar: { today: string; exam_date: string; days_until_exam: number; heatmap_start_date: string }
  private_display: { study_room_code: string; homepage_content: string; countdown_label: string }
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
  task_shortcuts: TaskShortcut[]
  tag_totals: Array<{ id: number; name: string; color: string; minutes: number; sessions: number }>
  task_totals: Array<{ subject: Subject; subject_label: string; path: string; minutes: number; sessions: number }>
  weekly_totals: Array<{ week_start: string; minutes: number }>
  monthly_totals: Array<{ month: string; minutes: number }>
  heatmap: HeatmapDay[]
  daily_start_times: Array<{ date: string; first_start: string }>
}

export interface RuntimeSettingsValues {
  homepage_content: string
  study_room_code: string
  tracking_start_date: string
  exam_date: string
  countdown_label: string
}

export interface RuntimeSettingsResponse {
  values: RuntimeSettingsValues
  defaults: RuntimeSettingsValues
  sources: Record<keyof RuntimeSettingsValues, 'local_env' | 'default'>
  fingerprint: string
  local_env_exists: boolean
  writable: boolean
}

export interface DataEncryptionStatus {
  enabled: boolean
  available: boolean
  algorithm: 'AES-256-GCM'
  mode: 'server-managed-at-rest'
  updated_at: string | null
  migrated_records?: number
}

export interface ReviewTrendDay { date: string; count: number }

export interface ReviewTrend {
  session_id: number
  session_uuid: string
  total: number
  last_reviewed_at: string | null
  review_days: number
  window_days: number
  created: boolean
  daily: ReviewTrendDay[]
}

export interface InviteCode {
  id: number
  name: string
  created_by: string
  is_active: boolean
  max_uses: number
  use_count: number
  remaining_uses: number
  expires_at: string | null
  last_used_at: string | null
  created_at: string
  usable: boolean
  is_self_service: boolean
  issued_local_date: string | null
  visitors: Array<{ username: string; redeemed_at: string }>
  raw_code?: string
  signup_url?: string
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
  is_paused: boolean
  available_from: string
  available_until: string
  expires_at: string | null
  max_uses: number | null
  usage_count: number
  source_label: string
  notes: string
  usable: boolean
  credential_valid: boolean
  within_schedule: boolean
  has_disturbance_uri: boolean
  raw_token?: string
  raw_disturbance_token?: string
  launch_url?: string
  shortcut_start_url?: string
  disturbance_url?: string
  shortcuts_create_url?: string
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
  session_uuid?: string
  title: string
  snippet: string
  subject: Subject
  subject_label: string
  occurred_at: string
}

export interface SessionShareStatus {
  status: 'private' | 'active' | 'expired' | 'revoked'
  is_shared: boolean
  is_active: boolean
  created_at: string | null
  expires_at: string | null
  revoked_at: string | null
  share_url?: string
  warning?: string
}

export interface PublicSharedSession {
  title: string
  subject: Subject
  start_time: string
  end_time: string | null
  duration_minutes: number
  markdown: string
}

export interface GlobalSearchResponse {
  query: string
  results: GlobalSearchResult[]
}
