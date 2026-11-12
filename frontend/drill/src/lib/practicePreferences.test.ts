// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
afterEach(() => { localStorage.clear(); vi.restoreAllMocks(); vi.resetModules() })
it('preserves existing defaults and shares live preferences between Settings and Question routes', async () => {
  const { usePracticePreferences } = await import('./practicePreferences')
  const question = usePracticePreferences('drill'), settings = usePracticePreferences('drill')
  expect(settings).toBe(question)
  expect(question.nextMode.value).toBe('sequential'); expect(question.masteredAutoNext.value).toBe(true)
  expect(question.reviewAutoNext.value).toBe(false); expect(question.pageTurnCopyMode.value).toBe('off')
  settings.reviewAutoNext.value = true; settings.nextMode.value = 'unattempted'
  expect(question.reviewAutoNext.value).toBe(true); expect(localStorage.getItem('drill.next-mode.v1')).toBe('unattempted')
})
it('retains the three shared legacy keys and isolates page-turn copying for each workspace', async () => {
  localStorage.setItem('drill.mastered-auto-next.v1', 'false')
  localStorage.setItem('drill.next-mode.v1', 'review')
  localStorage.setItem('ei.page-turn-copy.v1', 'image')
  const { usePracticePreferences } = await import('./practicePreferences')
  const drill = usePracticePreferences('drill'), ei = usePracticePreferences('ei')
  expect(ei.masteredAutoNext.value).toBe(false); expect(ei.nextMode.value).toBe('review')
  expect(drill.pageTurnCopyMode.value).toBe('off'); expect(ei.pageTurnCopyMode.value).toBe('image')
  drill.pageTurnCopyMode.value = 'link'; ei.reviewAutoNext.value = true
  expect(localStorage.getItem('drill.page-turn-copy.v1')).toBe('link')
  expect(localStorage.getItem('ei.page-turn-copy.v1')).toBe('image')
  expect(drill.reviewAutoNext.value).toBe(true)
})
it('keeps preferences usable when browser storage is denied', async () => {
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('denied') })
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('denied') })
  const { usePracticePreferences } = await import('./practicePreferences')
  const prefs = usePracticePreferences('ei')
  expect(() => { prefs.pageTurnCopyMode.value = 'image'; prefs.masteredAutoNext.value = false }).not.toThrow()
})
