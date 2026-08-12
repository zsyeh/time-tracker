import { describe, expect, it } from 'vitest'
import { elementComponents } from './elementComponents'

describe('Element Plus registrations', () => {
  it('registers task taxonomy controls used by Settings and Today', () => {
    const names = elementComponents.map((component) => component.name)
    expect(names).toContain('ElTree')
    expect(names).toContain('ElCascader')
  })
})
