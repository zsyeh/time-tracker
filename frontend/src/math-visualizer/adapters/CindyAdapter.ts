import type { ComplexScene, MathRenderer, MathScene, QualityProfile, RendererCapabilities } from '../types'
import { loadVendorScript } from '../core/vendorAssets'

interface CindyInstance {
  evokeCS(code: string): void
  pause?(): void
  play?(): void
  resize?(): void
  shutdown?(): void
}
type CindyFactory = (options: Record<string, unknown>) => CindyInstance

const cindyFunctions: Record<ComplexScene['preset'], string> = {
  identity: 'z', square: 'z^2', reciprocal: '1/z', exp: 'exp(z)', sin: 'sin(z)', cos: 'cos(z)', log: 'log(z)',
}

export class CindyAdapter implements MathRenderer {
  readonly id = 'cindy' as const
  readonly capabilities: RendererCapabilities = { supports3D: false, supportsComplexGpu: true, supportsInstancing: false, supportsWebGPU: false }
  private instance: CindyInstance | null = null
  private canvas!: HTMLCanvasElement
  private currentPreset = ''

  async init(container: HTMLElement) {
    await loadVendorScript('Cindy-0.0.5.js')
    await loadVendorScript('CindyGL-0.0.5.js')
    const factory = (window as Window & { CindyJS?: CindyFactory }).CindyJS
    if (!factory) throw new Error('CindyJS did not expose its browser runtime.')
    this.canvas = document.createElement('canvas')
    this.canvas.className = 'math-viewport-canvas'
    this.canvas.id = `cindy-math-${globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`}`
    container.replaceChildren(this.canvas)
    this.instance = factory({
      ports: [{ id: this.canvas.id, transform: [{ visibleRect: [-4, 4, 4, -4] }], background: 'rgb(9,13,17)' }],
      scripts: {
        init: 'f(z):=z^2;',
        draw: 'colorplot(w=f(complex(#)); m=abs(w); hue(arctan2(im(w),re(w))/(2*pi))*(0.32+0.68*(1-exp(-m))));',
      },
      geometry: [{ name: 'A', type: 'Free', pos: [1, 1, 1], color: [1, .7, .2], size: 5 }],
      use: ['CindyGL'],
      autoplay: true,
    })
  }

  resize(width: number, height: number, dpr: number) { this.canvas.width = Math.round(width * dpr); this.canvas.height = Math.round(height * dpr); this.canvas.style.width = `${width}px`; this.canvas.style.height = `${height}px`; this.instance?.resize?.() }
  setQuality(_profile: QualityProfile) { /* CindyGL manages its render target; viewport DPR is capped upstream. */ }
  render(scene: MathScene) { if (scene.kind !== 'complex' || !this.instance || scene.preset === this.currentPreset) return; this.instance.evokeCS(`f(z):=${cindyFunctions[scene.preset]};`); this.currentPreset = scene.preset }
  pause() { this.instance?.pause?.() }
  resume() { this.instance?.play?.() }
  dispose() { this.instance?.shutdown?.(); this.canvas?.remove(); this.instance = null }
}
