import FFT from 'fft.js'
import { signalValue } from './numerics'
import type { SignalPreset } from '../types'

/**
 * Returns the positive, integral-frequency half-spectrum. Values use the same
 * 1/N normalization as the Fourier integral shown in the UI.
 */
export function computeSpectrum(preset: SignalPreset, size = 1024): number[] {
  if (size < 2 || (size & (size - 1)) !== 0) throw new Error('FFT size must be a power of two greater than one.')
  const fft = new FFT(size)
  const input = Array.from({ length: size }, (_, index) => signalValue(preset, index / size))
  const output = fft.createComplexArray()
  fft.realTransform(output, input)
  return Array.from({ length: size / 2 + 1 }, (_, bin) => Math.hypot(output[bin * 2], output[bin * 2 + 1]) / size)
}
