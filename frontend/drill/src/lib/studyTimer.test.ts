// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { api } from './api'
import { activeStudyTimer, startStudyTimer } from './studyTimer'
vi.mock('./api', () => ({ api: vi.fn() }))
afterEach(() => { vi.resetAllMocks(); vi.useRealTimers() })

it('checks only the authenticated user’s running timer', async () => {
  vi.mocked(api).mockResolvedValueOnce({ results: [] }).mockResolvedValueOnce({ results: [{ id: 3, subject: 'math' }] })
  expect(await activeStudyTimer()).toBeNull()
  expect(await activeStudyTimer()).toEqual({ id: 3, subject: 'math' })
  expect(api).toHaveBeenCalledWith('/api/sessions/?status=running', expect.objectContaining({ signal: expect.any(AbortSignal) }))
})
it.each([['drill', 'math', 'Drill'], ['ei', 'major', 'EI']] as const)('starts %s using the existing subject/session API', async (workspace, subject, topic) => {
  vi.mocked(api).mockResolvedValue({ session: { id: 7, subject } })
  expect(await startStudyTimer(workspace)).toEqual({ id: 7, subject })
  const [url, options] = vi.mocked(api).mock.calls[0]!
  expect(url).toBe('/api/sessions/')
  expect(options?.method).toBe('POST')
  expect(JSON.parse(String(options?.body))).toEqual({ subject, topic, learning_mode: 'exercise' })
})
it('rejects an unexpected returned subject rather than treating it as started', async () => {
  vi.mocked(api).mockResolvedValue({ session: { id: 7, subject: 'english' } })
  await expect(startStudyTimer('ei')).rejects.toThrow('Unexpected study timer subject')
})
it('bounds an unresponsive check so answer saving remains recoverable', async () => {
  vi.useFakeTimers()
  vi.mocked(api).mockImplementation((_url, options) => new Promise((_resolve, reject) => {
    options?.signal?.addEventListener('abort', () => reject(new Error('aborted')))
  }))
  const result = expect(activeStudyTimer()).rejects.toThrow('aborted')
  await vi.advanceTimersByTimeAsync(4000)
  await result
})
