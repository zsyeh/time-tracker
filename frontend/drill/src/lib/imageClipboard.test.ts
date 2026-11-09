// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest'
import { copyImagesToClipboard, fittedCanvasSize } from './imageClipboard'

describe('question image clipboard layout', () => {
  it('stacks multiple images vertically at a shared width', () => {
    expect(fittedCanvasSize([
      { width: 1000, height: 500 },
      { width: 500, height: 500 },
    ])).toEqual({ width: 1000, height: 1500, scale: 1 })
  })

  it('scales oversized composites without cropping', () => {
    const result = fittedCanvasSize([
      { width: 10000, height: 10000 },
      { width: 10000, height: 10000 },
    ])
    expect(result.width).toBe(8192)
    expect(result.height).toBe(16384)
    expect(result.scale).toBeCloseTo(0.8192)
  })

  it('starts copying before a later question image URL is available', async () => {
    let resolveUrls!: (urls: string[]) => void
    const urls = new Promise<string[]>((resolve) => { resolveUrls = resolve })
    const copied: Array<Record<string, Promise<Blob>>> = []
    class TestClipboardItem {
      constructor(public data: Record<string, Promise<Blob>>) { copied.push(data) }
    }
    Object.defineProperty(window, 'ClipboardItem', { configurable: true, value: TestClipboardItem })
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { write: vi.fn().mockResolvedValue(undefined) },
    })
    const blob = new Blob(['png'], { type: 'image/png' })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, blob: () => Promise.resolve(blob) }))

    const result = copyImagesToClipboard(urls)
    expect(navigator.clipboard.write).toHaveBeenCalledTimes(1)
    resolveUrls(['/api/drill/assets/example/'])
    expect(await copied[0]['image/png']).toBe(blob)
    expect((await result).combined).toBe(false)
    vi.unstubAllGlobals()
  })
})
