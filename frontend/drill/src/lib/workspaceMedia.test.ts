// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { warmQuestionMedia } from './workspace'
import type { QuestionDetail } from '../types'
vi.mock('./api', () => ({ api: vi.fn() }))
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers() })
it('coalesces repeated warming, limits concurrent image loads and retries failed URLs', () => {
  const requested: string[] = []
  const images: Array<{ onload: (() => void) | null; onerror: (() => void) | null }> = []
  vi.stubGlobal('Image', class {
    onload: (() => void) | null = null
    onerror: (() => void) | null = null
    constructor() { images.push(this) }
    set src(url: string) { requested.push(url) }
  })
  const question = { question_assets: Array.from({ length: 8 }, (_, i) => ({ url: `/warm-${i}` })), answer_assets: [{ url: '/warm-0' }] } as QuestionDetail
  warmQuestionMedia(question); warmQuestionMedia(question)
  expect(requested).toHaveLength(4)
  images[0]!.onerror!(); expect(requested).toHaveLength(5)
  for (let i = 1; i < 8; i++) images[i]!.onload!()
  expect(requested).toHaveLength(8)
  warmQuestionMedia(question)
  expect(requested).toHaveLength(9)
  expect(requested[8]).toContain('/warm-0')
  images[8]!.onload!()
  warmQuestionMedia(question); expect(requested).toHaveLength(9)
})

it('releases stalled slots after a bounded timeout, permits retry and clears completion timers', () => {
  vi.useFakeTimers()
  const requested: string[] = []
  const images: Array<{ onload: (() => void) | null; onerror: (() => void) | null; removeAttribute: ReturnType<typeof vi.fn> }> = []
  vi.stubGlobal('Image', class {
    onload: (() => void) | null = null
    onerror: (() => void) | null = null
    removeAttribute = vi.fn()
    constructor() { images.push(this) }
    set src(url: string) { requested.push(url) }
  })
  const question = { question_assets: Array.from({ length: 5 }, (_, i) => ({ url: `/stalled-${i}` })) } as QuestionDetail
  warmQuestionMedia(question)
  expect(requested).toHaveLength(4)
  expect(vi.getTimerCount()).toBe(4)
  // Preserve a delayed callback to verify it cannot release the same slot twice.
  const lateLoad = images[0]!.onload!
  vi.advanceTimersByTime(15000)
  expect(requested).toHaveLength(5)
  expect(images[0]!.removeAttribute).toHaveBeenCalledWith('src')
  expect(images[0]!.onload).toBeNull()
  lateLoad()
  expect(vi.getTimerCount()).toBe(1)
  images[4]!.onload!()
  expect(vi.getTimerCount()).toBe(0)
  warmQuestionMedia(question)
  expect(requested).toHaveLength(9)
  for (let i = 5; i < 9; i++) images[i]!.onload!()
  expect(vi.getTimerCount()).toBe(0)
})
