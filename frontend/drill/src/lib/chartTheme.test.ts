// @vitest-environment jsdom
import { afterEach, expect, it } from 'vitest'
import { chartPalette } from './chartTheme'

afterEach(() => {
  document.querySelector('.drill-shell')?.remove()
  document.documentElement.style.removeProperty('--accent')
})

it('uses the active workspace accent for charts', () => {
  document.documentElement.style.setProperty('--accent', '#6ba6ff')
  const workspace = document.createElement('div')
  workspace.className = 'drill-shell ei-workspace'
  workspace.style.setProperty('--accent', '#79adf3')
  document.body.append(workspace)

  expect(chartPalette().accent).toBe('#79adf3')
  workspace.remove()
  expect(chartPalette().accent).toBe('#6ba6ff')
})
