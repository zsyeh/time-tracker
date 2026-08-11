import { describe, expect, it } from 'vitest'
import * as math from 'mathjs'
import { MathEngine } from './MathEngine'

describe('MathEngine expression boundary', () => {
  const engine = new MathEngine(math)

  it('evaluates approved scalar complex expressions', async () => {
    const value = await engine.evaluateComplex('z^2 + 1/z', { re: 1, im: 1 })
    expect(value.re).toBeCloseTo(.5, 8)
    expect(value.im).toBeCloseTo(1.5, 8)
  })

  it('rejects assignments and property traversal', async () => {
    await expect(engine.compile('x = 2')).rejects.toThrow(/not allowed/i)
    await expect(engine.compile('x.constructor')).rejects.toThrow(/not allowed/i)
  })

  it('samples a finite real surface without executable JavaScript', async () => {
    const sampled = await engine.sampleSurface('sin(x) * cos(y)', 9, 2)
    expect(sampled.values).toHaveLength(81)
    expect(sampled.values.every(Number.isFinite)).toBe(true)
  })
})
