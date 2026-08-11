import { mathVendorUrl } from '../core/vendorAssets'
import type { MathRenderer, MathScene, QualityProfile, RendererCapabilities } from '../types'

export class MathBoxAdapter implements MathRenderer {
  readonly id = 'mathbox' as const
  readonly capabilities: RendererCapabilities = { supports3D: true, supportsComplexGpu: false, supportsInstancing: false, supportsWebGPU: false }
  private iframe!: HTMLIFrameElement
  private container!: HTMLElement
  private profile!: QualityProfile
  private currentKey = ''
  private ready = false
  private resolveReady: (() => void) | null = null
  private rejectReady: ((reason: Error) => void) | null = null

  async init(container: HTMLElement) {
    this.container = container
    this.iframe = document.createElement('iframe')
    this.iframe.className = 'mathbox-isolated-frame'
    this.iframe.title = 'Isolated MathBox surface renderer'
    this.iframe.sandbox.add('allow-scripts', 'allow-same-origin')
    window.addEventListener('message', this.receiveMessage)
    container.replaceChildren(this.iframe)
    const initialized = new Promise<void>((resolve, reject) => { this.resolveReady = resolve; this.rejectReady = reject })
    const timeout = window.setTimeout(() => this.rejectReady?.(new Error('MathBox renderer timed out.')), 8_000)
    this.iframe.src = mathVendorUrl('mathbox-frame-v1.html')
    try { await initialized } finally { window.clearTimeout(timeout); this.resolveReady = null; this.rejectReady = null }
  }

  resize(width: number, height: number, dpr: number) { this.post({ type: 'mathbox-resize', width, height, dpr }) }
  setQuality(profile: QualityProfile) { this.profile = profile; this.currentKey = '' }

  render(scene: MathScene) {
    if (scene.kind !== 'surface' || !this.ready) return
    const resolution = Math.min(112, this.profile.surfaceResolution)
    const key = `${scene.preset}:${scene.expression}:${resolution}:${scene.wireframe}`
    if (key === this.currentKey) return
    const accent = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim() || '#10c469'
    this.post({ type: 'mathbox-scene', scene, resolution, accent })
    this.currentKey = key
  }

  pause() { this.post({ type: 'mathbox-pause' }) }
  resume() { this.post({ type: 'mathbox-resume' }) }
  dispose() {
    this.post({ type: 'mathbox-dispose' })
    window.removeEventListener('message', this.receiveMessage)
    this.iframe?.remove()
    this.ready = false
    this.currentKey = ''
  }

  private post(message: Record<string, unknown>) { this.iframe?.contentWindow?.postMessage(message, window.location.origin) }
  private receiveMessage = (event: MessageEvent) => {
    if (event.origin !== window.location.origin || event.source !== this.iframe?.contentWindow) return
    if (event.data?.type === 'mathbox-ready') { this.ready = true; this.resolveReady?.() }
    if (event.data?.type === 'mathbox-error') {
      const error = new Error(event.data.message || 'MathBox renderer failed.')
      if (!this.ready) this.rejectReady?.(error)
      else this.container.dispatchEvent(new CustomEvent('math-renderer-error', { bubbles: true, detail: error.message }))
    }
  }
}
