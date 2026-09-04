import { computed, ref } from 'vue'

export type UiLanguage = 'en' | 'zh-CN' | 'ja'
export type UiScheme = 'dark' | 'light'

const LANGUAGE_KEY = 'learning-os-ui-language'
const SCHEME_KEY = 'learning-os-color-scheme'
const LANGUAGE_COOKIE = 'learning_os_ui_language'
const SCHEME_COOKIE = 'learning_os_color_scheme'

const english = {
  language: 'Language', appearance: 'Appearance', dark: 'Dark', light: 'Light',
  search: 'Search', today: 'Today', workspace: 'Workspace', trends: 'Trends', sessions: 'Sessions', issues: 'Issues', subjects: 'Subjects',
  mathematics: 'Mathematics', english: 'English', major: 'Major / 892', training: 'Training', settings: 'Settings', account: 'Account', signOut: 'Sign out', hideSidebar: 'Hide sidebar',
  viewSession: 'View session', startSession: 'Start session', dailyProgress: 'Daily progress', completedOnly: 'Completed sessions only', firstStart: 'First start', currentStreak: 'Current streak', fiveHourStreak: '5H streak', session: 'Session', inProgress: 'In progress', chooseTask: 'Choose a subject or saved task', activity: 'Activity', consistency: 'Study consistency and daily drilldown', lastDays: 'Last {days} days',
  activeDays: 'Active days', fiveHourDays: '5H days', total: 'Total', targetComplete: 'Daily target complete', complete: 'Complete', remaining: '{value} left', toTarget: '{value} to the daily target', bestStreak: 'Best streak {days}d', examIn: 'Exam in {days} days', studyRoom: 'Study room', days: 'days',
  overview: 'Overview', averageFirstStart: 'Average first start', activeDaysOnly: 'Active days only', targetDays: '5H target days', totalCompleted: 'Total completed', recentWeeks: 'Recent weeks', recentMonths: 'Recent months', tags: 'Tags', tasks: 'Tasks', studyDistribution: 'Study distribution', daily: 'Daily', duration: 'Duration', weeks: 'weeks', months: 'months', ofTotal: 'of total', currentStreakLabel: '{days}-day current streak',
  records: '{count} records', allSessions: 'All sessions', filter: 'Filter', display: 'Display', view: 'View', searchSessions: 'Search sessions', allSubjects: 'All subjects', allStatuses: 'All statuses', status: 'Status', properties: 'Properties', visibleProperties: 'Visible properties', startTime: 'Start time', efficiency: 'Efficiency', groupBy: 'Group by', sortCurrentPage: 'Sort current page', density: 'Density', date: 'Date', newest: 'Newest', oldest: 'Oldest', compact: 'Compact', comfortable: 'Comfortable', currentPage: 'Current page', groupedBy: 'Grouped by {value}',
  active: 'Active', resolved: 'Resolved', all: 'All', openCount: '{count} active · {resolved} resolved', newIssue: 'New issue', searchIssues: 'Search issues', issueType: 'Issue type', allTypes: 'All types', repeatCount: 'Repeat count', noDescription: 'No description', resolution: 'Resolution', currentView: 'Current view', delete: 'Delete',
  preferencesAccess: 'Preferences and access', general: 'General', tracking: 'Tracking', organization: 'Organization', security: 'Security', access: 'Access', data: 'Data', automation: 'Automation', integrations: 'Integrations', invitations: 'Invitations', content: 'Content',
  backSessions: 'Sessions', sessionArticle: 'Session article', contextProperties: 'Properties', started: 'Started', ended: 'Ended', credited: 'Credited', actual: 'Actual', disturbances: 'Disturbances', reviewActivity: 'Review activity', publicShare: 'Public share', edit: 'Edit', createLink: 'Create link', copy: 'Copy', revoke: 'Revoke', private: 'Private', sessionInProgress: 'Session in progress', startRecorded: 'Start time recorded.', timerHidden: 'Timer hidden', visibleAfter: 'Visible after completion', discard: 'Discard', finishReview: 'Finish & review', selectTask: 'Select a task or subject.', automaticStart: 'Start time is recorded automatically. Duplicate starts are ignored.', browseTasks: 'Browse nested task presets', choosePreset: 'Choose a task preset', cancel: 'Cancel', startSelected: 'Start selected task', completeSession: 'Complete session', efficiencyAssessment: 'Efficiency assessment', creditedFormula: 'Credited time = actual duration × coefficient', titleOptional: 'Title · Optional', markdownOptional: 'Markdown details · Optional', recentNotes: 'Recent notes', emptyAllowed: 'You may leave both fields empty. Sessions under 25 minutes or over 12 hours are deleted automatically.', continueSession: 'Continue session', saveFinish: 'Save & finish',
} as const

type MessageKey = keyof typeof english
type Messages = Record<MessageKey, string>

const translations: Record<UiLanguage, Messages> = {
  en: english,
  'zh-CN': {
    language: '语言', appearance: '外观', dark: '深色', light: '浅色',
    search: '搜索', today: '今日', workspace: '工作区', trends: '趋势', sessions: '学习记录', issues: '问题', subjects: '学科',
    mathematics: '数学', english: '英语', major: '专业课 / 892', training: '训练', settings: '设置', account: '账户', signOut: '退出登录', hideSidebar: '隐藏侧栏',
    viewSession: '查看任务', startSession: '开始学习', dailyProgress: '今日进度', completedOnly: '仅统计已完成任务', firstStart: '首次开始', currentStreak: '连续天数', fiveHourStreak: '连续 5 小时日', session: '学习任务', inProgress: '进行中', chooseTask: '选择学科或预设任务', activity: '活动', consistency: '学习连续性与每日下钻', lastDays: '最近 {days} 天',
    activeDays: '活跃天数', fiveHourDays: '达标天数', total: '总计', targetComplete: '今日目标已完成', complete: '已完成', remaining: '还差 {value}', toTarget: '距离今日目标还差 {value}', bestStreak: '最佳连续 {days} 天', examIn: '距考试 {days} 天', studyRoom: '自习室', days: '天',
    overview: '概览', averageFirstStart: '平均开始时间', activeDaysOnly: '仅活跃日', targetDays: '5 小时达标日', totalCompleted: '累计完成', recentWeeks: '最近几周', recentMonths: '最近几月', tags: '标签', tasks: '任务', studyDistribution: '学习分布', daily: '每日', duration: '时长', weeks: '周', months: '月', ofTotal: '占总时长', currentStreakLabel: '当前连续 {days} 天',
    records: '共 {count} 条', allSessions: '全部记录', filter: '筛选', display: '显示', view: '视图', searchSessions: '搜索学习记录', allSubjects: '全部学科', allStatuses: '全部状态', status: '状态', properties: '属性', visibleProperties: '显示属性', startTime: '开始时间', efficiency: '效率', groupBy: '分组方式', sortCurrentPage: '当前页排序', density: '密度', date: '日期', newest: '最新优先', oldest: '最早优先', compact: '紧凑', comfortable: '舒适', currentPage: '当前页', groupedBy: '按{value}分组',
    active: '未解决', resolved: '已解决', all: '全部', openCount: '{count} 个未解决 · {resolved} 个已解决', newIssue: '新建问题', searchIssues: '搜索问题', issueType: '问题类型', allTypes: '全部类型', repeatCount: '重复次数', noDescription: '无描述', resolution: '解决方案', currentView: '当前视图', delete: '删除',
    preferencesAccess: '偏好、权限与数据', general: '通用', tracking: '追踪', organization: '组织', security: '安全', access: '访问', data: '数据', automation: '自动化', integrations: '集成', invitations: '邀请码', content: '内容',
    backSessions: '返回记录', sessionArticle: '学习文章', contextProperties: '属性', started: '开始', ended: '结束', credited: '计入时长', actual: '实际时长', disturbances: '扰动', reviewActivity: '回顾活动', publicShare: '公开分享', edit: '编辑', createLink: '创建链接', copy: '复制', revoke: '撤销', private: '私密', sessionInProgress: '学习进行中', startRecorded: '开始时间已记录。', timerHidden: '计时已隐藏', visibleAfter: '完成后显示', discard: '丢弃', finishReview: '完成并回顾', selectTask: '选择任务或学科', automaticStart: '开始时间会自动记录，重复启动将被忽略。', browseTasks: '浏览多级任务预设', choosePreset: '选择任务预设', cancel: '取消', startSelected: '开始所选任务', completeSession: '完成学习', efficiencyAssessment: '效率评估', creditedFormula: '计入时长 = 实际时长 × 系数', titleOptional: '标题 · 可选', markdownOptional: 'Markdown 详情 · 可选', recentNotes: '最近记录', emptyAllowed: '两个字段均可留空；少于 25 分钟或超过 12 小时的任务会自动删除。', continueSession: '继续学习', saveFinish: '保存并完成',
  },
  ja: {
    language: '言語', appearance: '外観', dark: 'ダーク', light: 'ライト',
    search: '検索', today: '今日', workspace: 'ワークスペース', trends: 'トレンド', sessions: 'セッション', issues: '課題', subjects: '科目',
    mathematics: '数学', english: '英語', major: '専門 / 892', training: 'トレーニング', settings: '設定', account: 'アカウント', signOut: 'ログアウト', hideSidebar: 'サイドバーを隠す',
    viewSession: 'セッションを見る', startSession: '学習を開始', dailyProgress: '今日の進捗', completedOnly: '完了したセッションのみ', firstStart: '開始時刻', currentStreak: '連続日数', fiveHourStreak: '5時間連続', session: 'セッション', inProgress: '進行中', chooseTask: '科目または保存済みタスクを選択', activity: 'アクティビティ', consistency: '学習の継続性と日別詳細', lastDays: '過去 {days} 日',
    activeDays: '活動日', fiveHourDays: '5時間達成日', total: '合計', targetComplete: '今日の目標を達成', complete: '完了', remaining: '残り {value}', toTarget: '今日の目標まで {value}', bestStreak: '最長 {days} 日', examIn: '試験まで {days} 日', studyRoom: '自習室', days: '日',
    overview: '概要', averageFirstStart: '平均開始時刻', activeDaysOnly: '活動日のみ', targetDays: '5時間達成日', totalCompleted: '累計完了', recentWeeks: '最近の週', recentMonths: '最近の月', tags: 'タグ', tasks: 'タスク', studyDistribution: '学習分布', daily: '日別', duration: '時間', weeks: '週間', months: 'か月', ofTotal: '合計に占める割合', currentStreakLabel: '現在 {days} 日連続',
    records: '{count} 件', allSessions: 'すべて', filter: 'フィルター', display: '表示', view: 'ビュー', searchSessions: 'セッションを検索', allSubjects: 'すべての科目', allStatuses: 'すべての状態', status: '状態', properties: 'プロパティ', visibleProperties: '表示する項目', startTime: '開始時刻', efficiency: '効率', groupBy: 'グループ化', sortCurrentPage: '現在のページを並べ替え', density: '密度', date: '日付', newest: '新しい順', oldest: '古い順', compact: 'コンパクト', comfortable: 'ゆったり', currentPage: '現在のページ', groupedBy: '{value}別',
    active: '未解決', resolved: '解決済み', all: 'すべて', openCount: '未解決 {count} · 解決済み {resolved}', newIssue: '課題を追加', searchIssues: '課題を検索', issueType: '課題タイプ', allTypes: 'すべてのタイプ', repeatCount: '繰り返し', noDescription: '説明なし', resolution: '解決策', currentView: '現在のビュー', delete: '削除',
    preferencesAccess: '設定とアクセス', general: '一般', tracking: 'トラッキング', organization: '整理', security: 'セキュリティ', access: 'アクセス', data: 'データ', automation: '自動化', integrations: '連携', invitations: '招待', content: 'コンテンツ',
    backSessions: 'セッション', sessionArticle: '学習記事', contextProperties: 'プロパティ', started: '開始', ended: '終了', credited: '計上時間', actual: '実時間', disturbances: '中断', reviewActivity: 'レビュー履歴', publicShare: '公開共有', edit: '編集', createLink: 'リンク作成', copy: 'コピー', revoke: '無効化', private: '非公開', sessionInProgress: 'セッション進行中', startRecorded: '開始時刻を記録しました。', timerHidden: 'タイマー非表示', visibleAfter: '完了後に表示', discard: '破棄', finishReview: '完了してレビュー', selectTask: 'タスクまたは科目を選択', automaticStart: '開始時刻は自動記録され、重複開始は無視されます。', browseTasks: '階層タスクを参照', choosePreset: 'タスクプリセットを選択', cancel: 'キャンセル', startSelected: '選択したタスクを開始', completeSession: 'セッションを完了', efficiencyAssessment: '効率評価', creditedFormula: '計上時間 = 実時間 × 係数', titleOptional: 'タイトル · 任意', markdownOptional: 'Markdown 詳細 · 任意', recentNotes: '最近のノート', emptyAllowed: '両方とも空欄にできます。25分未満または12時間超のセッションは自動削除されます。', continueSession: 'セッションを続ける', saveFinish: '保存して完了',
  },
}

function readCookie(name: string) {
  if (typeof document === 'undefined') return null
  const match = document.cookie.split('; ').find((item) => item.startsWith(`${name}=`))
  return match ? decodeURIComponent(match.slice(name.length + 1)) : null
}

function persist(name: string, storageKey: string, value: string) {
  try { localStorage.setItem(storageKey, value) } catch { /* Storage may be unavailable in private contexts. */ }
  if (typeof document === 'undefined') return
  const sharedDomain = location.hostname === 'ehzsy.site' || location.hostname.endsWith('.ehzsy.site')
    ? '; Domain=.ehzsy.site'
    : ''
  document.cookie = `${name}=${encodeURIComponent(value)}; Path=/; Max-Age=31536000; SameSite=Lax${sharedDomain}`
}

function storedValue(cookieName: string, storageKey: string) {
  const cookie = readCookie(cookieName)
  if (cookie) return cookie
  try { return localStorage.getItem(storageKey) } catch { return null }
}

function storedLanguage(): UiLanguage {
  const value = storedValue(LANGUAGE_COOKIE, LANGUAGE_KEY)
  return value === 'zh-CN' || value === 'ja' ? value : 'en'
}

function storedScheme(): UiScheme {
  return storedValue(SCHEME_COOKIE, SCHEME_KEY) === 'light' ? 'light' : 'dark'
}

export const uiLanguage = ref<UiLanguage>(storedLanguage())
export const uiScheme = ref<UiScheme>(storedScheme())

function applyPreferences() {
  document.documentElement.dataset.colorScheme = uiScheme.value
  document.documentElement.lang = uiLanguage.value
  document.documentElement.style.colorScheme = uiScheme.value
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', uiScheme.value === 'light' ? '#f7f7f8' : '#101012')
}

export function setUiLanguage(value: UiLanguage) {
  uiLanguage.value = value
  persist(LANGUAGE_COOKIE, LANGUAGE_KEY, value)
  applyPreferences()
}

export function setUiScheme(value: UiScheme) {
  uiScheme.value = value
  persist(SCHEME_COOKIE, SCHEME_KEY, value)
  applyPreferences()
}

export function initializeUiPreferences() { applyPreferences() }

export function useUiPreferences() {
  const messages = computed(() => translations[uiLanguage.value])
  function t(key: MessageKey, values: Record<string, string | number> = {}) {
    let text: string = messages.value[key]
    Object.entries(values).forEach(([name, value]) => { text = text.replaceAll(`{${name}}`, String(value)) })
    return text
  }
  return { language: uiLanguage, scheme: uiScheme, setLanguage: setUiLanguage, setScheme: setUiScheme, t }
}
