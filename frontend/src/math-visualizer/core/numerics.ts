import type { ComplexPreset, LaplacePreset, Matrix2, SignalPreset, SurfacePreset, SurfaceScene, Vec2 } from '../types'

export interface ComplexValue { re: number; im: number }
export interface EigenDirection { value: number; vector: Vec2 }

export function determinant([a, b, c, d]: Matrix2) { return a * d - b * c }

export function transform([a, b, c, d]: Matrix2, [x, y]: Vec2): Vec2 {
  return [a * x + b * y, c * x + d * y]
}

export function interpolateMatrix(matrix: Matrix2, t: number): Matrix2 {
  const [a, b, c, d] = matrix
  return [1 + (a - 1) * t, b * t, c * t, 1 + (d - 1) * t]
}

export function eigenDirections([a, b, c, d]: Matrix2): EigenDirection[] {
  const trace = a + d
  const discriminant = trace * trace - 4 * (a * d - b * c)
  if (discriminant < -1e-10) return []
  const root = Math.sqrt(Math.max(0, discriminant))
  const values = root < 1e-10 ? [trace / 2] : [(trace + root) / 2, (trace - root) / 2]
  return values.map((value) => {
    let x = b
    let y = value - a
    if (Math.hypot(x, y) < 1e-9) { x = value - d; y = c }
    if (Math.hypot(x, y) < 1e-9) { x = 1; y = 0 }
    const length = Math.hypot(x, y)
    return { value, vector: [x / length, y / length] as Vec2 }
  })
}

export function complexMultiply(a: ComplexValue, b: ComplexValue): ComplexValue {
  return { re: a.re * b.re - a.im * b.im, im: a.re * b.im + a.im * b.re }
}

export function complexExp(z: ComplexValue): ComplexValue {
  const radius = Math.exp(Math.max(-30, Math.min(30, z.re)))
  return { re: radius * Math.cos(z.im), im: radius * Math.sin(z.im) }
}

export function evaluateComplex(preset: ComplexPreset, z: ComplexValue): ComplexValue | null {
  const radiusSquared = z.re * z.re + z.im * z.im
  switch (preset) {
    case 'identity': return z
    case 'square': return complexMultiply(z, z)
    case 'reciprocal': return radiusSquared < 1e-8 ? null : { re: z.re / radiusSquared, im: -z.im / radiusSquared }
    case 'exp': return complexExp(z)
    case 'sin': {
      const expIz = complexExp({ re: -z.im, im: z.re })
      const expMinusIz = complexExp({ re: z.im, im: -z.re })
      return { re: (expIz.im - expMinusIz.im) / 2, im: -(expIz.re - expMinusIz.re) / 2 }
    }
    case 'cos': {
      const expIz = complexExp({ re: -z.im, im: z.re })
      const expMinusIz = complexExp({ re: z.im, im: -z.re })
      return { re: (expIz.re + expMinusIz.re) / 2, im: (expIz.im + expMinusIz.im) / 2 }
    }
    case 'log': return radiusSquared < 1e-8 ? null : { re: Math.log(Math.sqrt(radiusSquared)), im: Math.atan2(z.im, z.re) }
  }
}

export function signalValue(preset: SignalPreset, t: number): number {
  switch (preset) {
    case 'sine': return Math.sin(2 * Math.PI * 3 * t)
    case 'two-tone': return .65 * Math.sin(2 * Math.PI * 2 * t) + .35 * Math.sin(2 * Math.PI * 7 * t)
    case 'square': return Math.sin(2 * Math.PI * 3 * t) >= 0 ? 1 : -1
    case 'triangle': return 2 * Math.asin(Math.sin(2 * Math.PI * 3 * t)) / Math.PI
  }
}

export function fourierCoefficient(preset: SignalPreset, frequency: number, samples = 1024): ComplexValue {
  let re = 0
  let im = 0
  for (let index = 0; index < samples; index += 1) {
    const t = (index + .5) / samples
    const signal = signalValue(preset, t)
    const phase = -2 * Math.PI * frequency * t
    re += signal * Math.cos(phase)
    im += signal * Math.sin(phase)
  }
  return { re: re / samples, im: im / samples }
}

export function laplaceSignal(preset: LaplacePreset, t: number): number {
  switch (preset) {
    case 'constant': return 1
    case 'exponential': return Math.exp(.7 * t)
    case 'sine': return Math.sin(2 * t)
    case 'pulse': return t <= 2 ? 1 : 0
  }
}

export function numericalLaplace(preset: LaplacePreset, sigma: number, omega: number, maxTime = 18, samples = 4096): ComplexValue {
  const dt = maxTime / samples
  let re = 0
  let im = 0
  for (let index = 0; index < samples; index += 1) {
    const t = (index + .5) * dt
    const weighted = laplaceSignal(preset, t) * Math.exp(-sigma * t)
    re += weighted * Math.cos(omega * t) * dt
    im -= weighted * Math.sin(omega * t) * dt
  }
  return { re, im }
}

export function surfaceValue(preset: SurfacePreset, x: number, y: number): number {
  switch (preset) {
    case 'ripple': return Math.sin(x * x + y * y) / (1 + .12 * (x * x + y * y))
    case 'saddle': return .22 * (x * x - y * y)
    case 'gaussian': return 2.2 * Math.exp(-.35 * (x * x + y * y))
    case 'waves': return Math.sin(x) * Math.cos(y)
  }
}

export function sampleSurfaceScene(scene: SurfaceScene, x: number, y: number): number {
  const grid = scene.sampleGrid
  if (!grid) return surfaceValue(scene.preset, x, y)
  const coordinateX = Math.max(0, Math.min(grid.resolution - 1, (x + grid.range) / (grid.range * 2) * (grid.resolution - 1)))
  const coordinateY = Math.max(0, Math.min(grid.resolution - 1, (y + grid.range) / (grid.range * 2) * (grid.resolution - 1)))
  const x0 = Math.floor(coordinateX); const y0 = Math.floor(coordinateY)
  const x1 = Math.min(grid.resolution - 1, x0 + 1); const y1 = Math.min(grid.resolution - 1, y0 + 1)
  const tx = coordinateX - x0; const ty = coordinateY - y0
  const at = (column: number, row: number) => grid.values[row * grid.resolution + column] || 0
  return at(x0, y0) * (1 - tx) * (1 - ty) + at(x1, y0) * tx * (1 - ty) + at(x0, y1) * (1 - tx) * ty + at(x1, y1) * tx * ty
}

export function approximately(a: number, b: number, tolerance = 1e-6) {
  return Math.abs(a - b) <= tolerance
}
