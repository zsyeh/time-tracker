import { computed, ref } from 'vue'

export type UiLanguage = 'en' | 'zh-CN' | 'ja'
export type UiScheme = 'dark' | 'light'

const LANGUAGE_KEY = 'learning-os-ui-language'
const SCHEME_KEY = 'learning-os-color-scheme'
const LANGUAGE_COOKIE = 'learning_os_ui_language'
const SCHEME_COOKIE = 'learning_os_color_scheme'

const english = {
  practice: 'Practice', activity: 'Activity', bookActivity: 'Book Check-ins', knowledge: 'Knowledge', buildPaper: 'Build Paper', favorites: 'Favorites', nextTime: 'Next Time', bookFeel: 'Book Feel', insight: 'Insight',
  coverage: 'Your coverage', attempts: '{count} attempts', questionSources: 'Question sources', signOut: 'Sign out', appearance: 'Appearance', dark: 'Dark', light: 'Light', language: 'Language', dailyPractice: 'Daily practice', practiceActivity: 'Practice activity', bookCheckins: 'Book check-ins', knowledgeMap: 'Knowledge map', coverageByBook: 'Coverage by book', practiceRecency: 'Practice recency', questionSelection: 'Question selection', customPaper: 'Custom paper', generatePaper: 'Generate paper', generating: 'Generating…', questionIndex: 'Question index', foundationBank: '892 foundation bank', electronicInformation: 'Electronic information', questionBank: 'Question bank', resumeLast: 'Resume last question', openNext: 'Open next question', yourActivity: 'Your activity',
} as const
type MessageKey = keyof typeof english
type Messages = Record<MessageKey, string>
const translations: Record<UiLanguage, Messages> = {
  en: english,
  'zh-CN': {
    practice: '练习', activity: '活跃记录', bookActivity: '书目打卡', knowledge: '知识点', buildPaper: '组卷', favorites: '收藏', nextTime: '下次再看', bookFeel: '书目手感', insight: '洞察',
    coverage: '你的覆盖率', attempts: '{count} 次作答', questionSources: '题目来源', signOut: '退出登录', appearance: '外观', dark: '深色', light: '浅色', language: '语言', dailyPractice: '每日练习', practiceActivity: '练习活跃度', bookCheckins: '书目打卡', knowledgeMap: '知识图谱', coverageByBook: '按书目查看覆盖率', practiceRecency: '练习新鲜度', questionSelection: '题目选择', customPaper: '自定义组卷', generatePaper: '生成试卷', generating: '生成中…', questionIndex: '题目索引', foundationBank: '892 基础题库', electronicInformation: '电子信息', questionBank: '题库', resumeLast: '继续上一题', openNext: '打开下一题', yourActivity: '你的活动',
  },
  ja: {
    practice: '練習', activity: 'アクティビティ', bookActivity: '教材チェックイン', knowledge: '知識', buildPaper: '問題セット', favorites: 'お気に入り', nextTime: '次回', bookFeel: '教材の感覚', insight: 'インサイト',
    coverage: 'カバー率', attempts: '{count} 回', questionSources: '問題の出典', signOut: 'ログアウト', appearance: '外観', dark: 'ダーク', light: 'ライト', language: '言語', dailyPractice: '毎日の練習', practiceActivity: '練習アクティビティ', bookCheckins: '教材チェックイン', knowledgeMap: '知識マップ', coverageByBook: '教材別カバー率', practiceRecency: '練習の鮮度', questionSelection: '問題選択', customPaper: 'カスタム問題セット', generatePaper: '問題セットを作成', generating: '作成中…', questionIndex: '問題一覧', foundationBank: '892 基礎問題集', electronicInformation: '電子情報', questionBank: '問題集', resumeLast: '前回の問題を再開', openNext: '次の問題を開く', yourActivity: 'あなたの活動',
  },
}

function readCookie(name: string) {
  const match = document.cookie.split('; ').find((item) => item.startsWith(`${name}=`))
  return match ? decodeURIComponent(match.slice(name.length + 1)) : null
}
function stored(cookieName: string, storageKey: string) {
  const cookie = readCookie(cookieName)
  if (cookie) return cookie
  try { return localStorage.getItem(storageKey) } catch { return null }
}
function persist(cookieName: string, storageKey: string, value: string) {
  try { localStorage.setItem(storageKey, value) } catch { /* Browser storage can be restricted. */ }
  const sharedDomain = location.hostname === 'ehzsy.site' || location.hostname.endsWith('.ehzsy.site') ? '; Domain=.ehzsy.site' : ''
  document.cookie = `${cookieName}=${encodeURIComponent(value)}; Path=/; Max-Age=31536000; SameSite=Lax${sharedDomain}`
}

const initialLanguage = stored(LANGUAGE_COOKIE, LANGUAGE_KEY)
export const uiLanguage = ref<UiLanguage>(initialLanguage === 'zh-CN' || initialLanguage === 'ja' ? initialLanguage : 'en')
export const uiScheme = ref<UiScheme>(stored(SCHEME_COOKIE, SCHEME_KEY) === 'light' ? 'light' : 'dark')

function apply() {
  document.documentElement.dataset.colorScheme = uiScheme.value
  document.documentElement.lang = uiLanguage.value
  document.documentElement.style.colorScheme = uiScheme.value
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', uiScheme.value === 'light' ? '#f7f7f8' : '#101012')
}
export function initializeUiPreferences() { apply() }
export function useUiPreferences() {
  const messages = computed(() => translations[uiLanguage.value])
  function setLanguage(value: UiLanguage) { uiLanguage.value = value; persist(LANGUAGE_COOKIE, LANGUAGE_KEY, value); apply() }
  function setScheme(value: UiScheme) { uiScheme.value = value; persist(SCHEME_COOKIE, SCHEME_KEY, value); apply() }
  function t(key: MessageKey, values: Record<string, string | number> = {}) {
    let text: string = messages.value[key]
    Object.entries(values).forEach(([name, value]) => { text = text.replaceAll(`{${name}}`, String(value)) })
    return text
  }
  return { language: uiLanguage, scheme: uiScheme, setLanguage, setScheme, t }
}
