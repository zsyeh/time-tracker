import type { QualityMode, QualityProfile, QualityTier, RuntimeCapabilities } from '../types'

export const qualityProfiles: Record<QualityTier, QualityProfile> = {
  compatibility: { tier: 'compatibility', targetFps: 30, maxDpr: 1, curveSamples: 280, surfaceResolution: 26, vectorFieldDensity: 12, complexResolution: 224, enableGpuEvaluation: false, enableAntialias: false },
  low: { tier: 'low', targetFps: 40, maxDpr: 1, curveSamples: 520, surfaceResolution: 48, vectorFieldDensity: 18, complexResolution: 384, enableGpuEvaluation: true, enableAntialias: false },
  balanced: { tier: 'balanced', targetFps: 60, maxDpr: 1.5, curveSamples: 1000, surfaceResolution: 88, vectorFieldDensity: 30, complexResolution: 672, enableGpuEvaluation: true, enableAntialias: true },
  high: { tier: 'high', targetFps: 90, maxDpr: 2, curveSamples: 2200, surfaceResolution: 160, vectorFieldDensity: 48, complexResolution: 1024, enableGpuEvaluation: true, enableAntialias: true },
}

export function autoTier(capabilities: RuntimeCapabilities): QualityTier {
  if (!capabilities.canvas2d) return 'compatibility'
  if (!capabilities.webgl1) return 'compatibility'
  const cores = capabilities.hardwareConcurrency || 4
  const memory = capabilities.deviceMemoryGb || 4
  if (!capabilities.webgl2 || cores <= 4 || memory <= 3) return 'low'
  if (capabilities.webgpu && cores >= 8 && memory >= 8 && !capabilities.reducedMotion) return 'high'
  return 'balanced'
}

export function resolveQuality(mode: QualityMode, capabilities: RuntimeCapabilities): QualityProfile {
  return qualityProfiles[mode === 'auto' ? autoTier(capabilities) : mode]
}
