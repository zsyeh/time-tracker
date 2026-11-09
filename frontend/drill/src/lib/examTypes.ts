import { uiLanguage } from './uiPreferences'
import { ref } from 'vue'
export const formatColours = ref(true)

export type ExamType = 'choice' | 'fill' | 'judgment' | 'short_answer' | 'large' | 'unknown'
export type TypeStats = Record<string, { total: number; attempted: number; mastered: number; review: number }>
export const typeGroups = ['small', 'large', 'short_answer', 'unknown'] as const
const labels: Record<string, [string, string]> = {
  all: ['全部题型', 'All formats'], small: ['小题', 'Short questions'], large: ['大题', 'Worked solutions'],
  short_answer: ['简答题', 'Short answer'], unknown: ['题型待定', 'Unknown format'],
  choice: ['选择题', 'Choice'], fill: ['填空题', 'Fill in'], judgment: ['判断题', 'True / false'],
}
export function typeLabel(value: string) { return (labels[value] || labels.unknown)![uiLanguage.value === 'zh-CN' ? 0 : 1] }
export function typeText(zh: string, en: string) { return uiLanguage.value === 'zh-CN' ? zh : en }
