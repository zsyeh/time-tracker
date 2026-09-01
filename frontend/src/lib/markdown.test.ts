// @vitest-environment jsdom

import { describe, expect, it } from 'vitest'

import { renderMarkdown } from './markdown'

describe('renderMarkdown security', () => {
  it('renders inline and display TeX used by EI questions', () => {
    const rendered = renderMarkdown([
      '某电阻两端电压为 $12\\,\\text{V}$，电流为 $2\\,\\text{A}$。',
      '',
      '$$R=\\frac{U}{I}=6\\,\\Omega$$',
    ].join('\n'))
    const container = document.createElement('div')
    container.innerHTML = rendered

    expect(container.querySelectorAll('.katex').length).toBe(3)
    expect(container.querySelector('.katex-display')).not.toBeNull()
    expect(container.textContent).toContain('12')
    expect(container.textContent).toContain('R')
  })

  it('keeps shared Markdown inert while preserving safe links', () => {
    const rendered = renderMarkdown([
      '<script>window.pwned = true</script>',
      '<img src="x" onerror="window.pwned = true">',
      '[unsafe](javascript:window.pwned=true)',
      '[safe](https://example.com/article)',
    ].join('\n\n'))

    const container = document.createElement('div')
    container.innerHTML = rendered

    expect(container.querySelector('script')).toBeNull()
    expect(container.querySelector('[onerror]')).toBeNull()
    expect([...container.querySelectorAll('a')].some((link) => (
      link.getAttribute('href')?.startsWith('javascript:')
    ))).toBe(false)

    const safeLink = container.querySelector('a[href="https://example.com/article"]')
    expect(safeLink?.getAttribute('target')).toBe('_blank')
    expect(safeLink?.getAttribute('rel')).toBe('noopener noreferrer nofollow')
  })
})
