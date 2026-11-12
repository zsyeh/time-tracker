import { afterEach, expect, it, vi } from 'vitest'
import { createPreviewRangeLoader } from './rangeLoader'
afterEach(() => vi.useRealTimers())
it('requests only the final range after scrubbing through 5000 questions', async () => {
 vi.useFakeTimers()
 const load = vi.fn(async (_offset: number, _signal: AbortSignal) => {})
 const loader = createPreviewRangeLoader({cached: () => false, load})
 for (let index = 0; index < 5000; index += 50) loader.schedule(index, index + 19, index)
 expect(load).not.toHaveBeenCalled()
 await vi.advanceTimersByTimeAsync(48)
 expect(load).toHaveBeenCalledTimes(1)
 expect(load.mock.calls[0]?.[0]).toBe(4950)
 loader.dispose()
})
it('aborts obsolete batches and prioritizes the actual viewport over overscan', async () => {
 vi.useFakeTimers()
 const calls: Array<{offset:number;signal:AbortSignal}> = []
 const load = vi.fn((offset:number,signal:AbortSignal) => { calls.push({offset,signal}); return new Promise<void>(() => {}) })
 const loader = createPreviewRangeLoader({cached: () => false, load})
 loader.schedule(0,99,50); await vi.advanceTimersByTimeAsync(48)
 expect(calls.map(c => c.offset)).toEqual([50,0])
 loader.schedule(4950,4999,4975)
 expect(calls.every(c => c.signal.aborted)).toBe(true)
 await vi.advanceTimersByTimeAsync(48)
 expect(calls.at(-1)?.offset).toBe(4950)
 loader.dispose()
})
it('reuses cached batches without fetching them on reverse scrolling', async () => {
 vi.useFakeTimers()
 const load = vi.fn(async (_offset: number, _signal: AbortSignal) => {})
 const loader = createPreviewRangeLoader({cached: offset => offset === 100, load})
 loader.schedule(100,149,120); await vi.advanceTimersByTimeAsync(48)
 expect(load).not.toHaveBeenCalled(); loader.dispose()
})
