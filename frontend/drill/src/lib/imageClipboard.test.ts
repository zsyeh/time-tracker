// @vitest-environment jsdom
import { describe, expect, it } from 'vitest'
import { fittedCanvasSize } from './imageClipboard'

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
})
