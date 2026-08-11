import type { MathRenderer, MathScene, QualityProfile, RendererId, RuntimeCapabilities } from '../types'

export function selectRenderer(scene: MathScene, profile: QualityProfile, capabilities: RuntimeCapabilities): RendererId {
  if (profile.tier === 'compatibility' || !capabilities.webgl1) return 'canvas'
  if (scene.kind === 'complex' && scene.domainColoring && (profile.tier === 'balanced' || profile.tier === 'high') && profile.enableGpuEvaluation) return 'cindy'
  if (scene.kind === 'surface' && profile.tier === 'high' && capabilities.webgl2) return 'three-webgl'
  if (scene.kind === 'surface' && profile.tier === 'balanced' && capabilities.webgl1) return 'mathbox'
  return 'canvas'
}

export async function createRenderer(id: RendererId): Promise<MathRenderer> {
  switch (id) {
    case 'cindy': return new (await import('../adapters/CindyAdapter')).CindyAdapter()
    case 'mathbox': return new (await import('../adapters/MathBoxAdapter')).MathBoxAdapter()
    case 'three-webgl': return new (await import('./ThreeRenderer')).ThreeRenderer()
    default: return new (await import('./CanvasRenderer')).CanvasRenderer()
  }
}
