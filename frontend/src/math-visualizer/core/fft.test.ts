import { describe, expect, it } from 'vitest'
import { computeSpectrum } from './fft'

describe('FFT spectrum', () => {
  it('places the single-sine energy at 3 Hz', () => {
    const spectrum = computeSpectrum('sine', 1024)
    expect(spectrum[3]).toBeCloseTo(.5, 5)
    expect(spectrum[5]).toBeLessThan(.001)
  })

  it('rejects sizes that cannot use the radix FFT', () => {
    expect(() => computeSpectrum('sine', 1000)).toThrow(/power of two/i)
  })
})
