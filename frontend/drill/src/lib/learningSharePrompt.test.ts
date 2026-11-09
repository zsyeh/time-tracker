import { describe, expect, it } from 'vitest'
import { learningSharePrompt } from './learningSharePrompt'

describe('AI share prompt language', () => {
  const url = 'https://ei.ehzsy.site/share/learning/example/index.md'

  it('copies the selected workspace URL and evidence requirement in Chinese', () => {
    const prompt = learningSharePrompt('ei', url, 'zh-CN')
    expect(prompt).toContain(url)
    expect(prompt).toContain('EI')
    expect(prompt).toContain('不要编造')
  })

  it('uses English for the English interface', () => {
    const prompt = learningSharePrompt('ei', url, 'en')
    expect(prompt).toContain(url)
    expect(prompt).toContain('15 questions')
    expect(prompt).toContain('Do not invent')
    expect(prompt).not.toContain('请读取')
  })

  it('keeps the Drill workspace name when the same panel is used there', () => {
    expect(learningSharePrompt('drill', url, 'en')).toContain('DRILL learning-data link')
  })
})
