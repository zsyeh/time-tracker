import type { UiLanguage } from './uiPreferences'

export function learningSharePrompt(workspace: string, url: string, language: UiLanguage): string {
  const name = workspace.toUpperCase()
  if (language === 'zh-CN') {
    return `请读取这个 ${name} 学习数据链接：${url}。沿着目录查看热力图、错误分类和重点题目，根据真实数据分析我的薄弱点，并推荐明天需要练习的 15 道题。不要编造题目数量或掌握情况。`
  }
  return `Read this ${name} learning-data link: ${url}. Follow the directory to inspect the heatmap, error categories, and important questions. Analyze my weak areas using the actual data, then recommend 15 questions to practice tomorrow. Do not invent question counts or mastery status.`
}
