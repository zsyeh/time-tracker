// @vitest-environment jsdom

import { describe, expect, it } from 'vitest'

import { renderMarkdown } from './markdown'

describe('renderMarkdown security', () => {
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
