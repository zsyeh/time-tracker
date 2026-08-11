export type Vec2 = readonly [number, number]
export type Vec3 = readonly [number, number, number]
export type Matrix2 = readonly [number, number, number, number]

export type MathModuleId = 'linear' | 'complex' | 'fourier' | 'laplace' | 'surface'
export type QualityMode = 'auto' | 'compatibility' | 'low' | 'balanced' | 'high'
export type QualityTier = Exclude<QualityMode, 'auto'>

export interface RuntimeCapabilities {
  webgpu: boolean
  webgl2: boolean
  webgl1: boolean
  canvas2d: boolean
  reducedMotion: boolean
  devicePixelRatio: number
  hardwareConcurrency?: number
  deviceMemoryGb?: number
}

export interface QualityProfile {
  tier: QualityTier
  targetFps: number
  maxDpr: number
  curveSamples: number
  surfaceResolution: number
  vectorFieldDensity: number
  complexResolution: number
  enableGpuEvaluation: boolean
  enableAntialias: boolean
}

export interface LinearScene {
  kind: 'linear'
  matrix: Matrix2
  vector: Vec2
  showGrid: boolean
  showSquare: boolean
  showEigenvectors: boolean
}

export type ComplexPreset = 'identity' | 'square' | 'reciprocal' | 'exp' | 'sin' | 'cos' | 'log'
export interface ComplexScene {
  kind: 'complex'
  preset: ComplexPreset
  expression: string
  point: Vec2
  showGrid: boolean
  domainColoring: boolean
}

export type SignalPreset = 'sine' | 'two-tone' | 'square' | 'triangle'
export interface FourierScene {
  kind: 'fourier'
  preset: SignalPreset
  omega: number
  showWrapping: boolean
  showSpectrum: boolean
  spectrum: readonly number[]
}

export type LaplacePreset = 'constant' | 'exponential' | 'sine' | 'pulse'
export interface LaplaceScene {
  kind: 'laplace'
  preset: LaplacePreset
  sigma: number
  omega: number
}

export type SurfacePreset = 'ripple' | 'saddle' | 'gaussian' | 'waves'
export interface SurfaceScene {
  kind: 'surface'
  preset: SurfacePreset
  expression: string
  wireframe: boolean
  autoRotate: boolean
  sampleGrid?: {
    resolution: number
    range: number
    values: readonly number[]
  }
}

export type MathScene = LinearScene | ComplexScene | FourierScene | LaplaceScene | SurfaceScene
export type RendererId = 'canvas' | 'cindy' | 'mathbox' | 'three-webgl'

export interface RendererCapabilities {
  supports3D: boolean
  supportsComplexGpu: boolean
  supportsInstancing: boolean
  supportsWebGPU: boolean
}

export interface RendererTelemetry {
  renderer: RendererId
  fps: number
  frameTime: number
  width: number
  height: number
  dpr: number
}

export interface MathRenderer {
  readonly id: RendererId
  readonly capabilities: RendererCapabilities
  init(container: HTMLElement): Promise<void>
  resize(width: number, height: number, dpr: number): void
  setQuality(profile: QualityProfile): void
  render(scene: MathScene, time: number): void
  pause(): void
  resume(): void
  dispose(): void
}
