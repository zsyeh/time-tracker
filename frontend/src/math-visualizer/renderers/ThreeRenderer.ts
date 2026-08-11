import { sampleSurfaceScene } from '../core/numerics'
import type { MathRenderer, MathScene, QualityProfile, RendererCapabilities, SurfaceScene } from '../types'

export class ThreeRenderer implements MathRenderer {
  readonly id = 'three-webgl' as const
  readonly capabilities: RendererCapabilities = { supports3D: true, supportsComplexGpu: false, supportsInstancing: true, supportsWebGPU: false }
  private three: typeof import('three-modern') | null = null
  private renderer: import('three-modern').WebGLRenderer | null = null
  private camera: import('three-modern').PerspectiveCamera | null = null
  private scene3d: import('three-modern').Scene | null = null
  private mesh: import('three-modern').Mesh | null = null
  private controls: { update(): void; dispose(): void; enabled: boolean } | null = null
  private profile!: QualityProfile
  private width = 1
  private height = 1
  private dpr = 1
  private currentPreset = ''
  private currentResolution = 0
  private paused = false

  async init(container: HTMLElement) {
    const [three, controlsModule] = await Promise.all([
      import('three-modern'),
      import('three-modern/addons/controls/OrbitControls.js'),
    ])
    this.three = three
    this.scene3d = new three.Scene()
    this.scene3d.background = new three.Color('#090d11')
    this.camera = new three.PerspectiveCamera(42, 1, .1, 100)
    this.camera.position.set(7.2, 5.4, 7.2)
    this.renderer = new three.WebGLRenderer({ antialias: this.profile?.enableAntialias ?? true, powerPreference: 'high-performance' })
    this.renderer.outputColorSpace = three.SRGBColorSpace
    this.renderer.domElement.className = 'math-viewport-canvas'
    this.renderer.domElement.addEventListener('webglcontextlost', this.contextLost)
    this.renderer.domElement.addEventListener('webglcontextrestored', this.contextRestored)
    container.replaceChildren(this.renderer.domElement)
    const controls = new controlsModule.OrbitControls(this.camera, this.renderer.domElement)
    controls.enableDamping = true
    controls.dampingFactor = .08
    controls.target.set(0, 0, 0)
    this.controls = controls
    this.scene3d.add(new three.HemisphereLight(0xddeeff, 0x18201d, 2.1))
    const key = new three.DirectionalLight(0xffffff, 2.5)
    key.position.set(4, 7, 5)
    this.scene3d.add(key)
    this.scene3d.add(new three.GridHelper(10, 20, 0x47535d, 0x222a31))
  }

  resize(width: number, height: number, dpr: number) {
    if (!this.renderer || !this.camera) return
    this.width = Math.max(1, width); this.height = Math.max(1, height); this.dpr = Math.min(dpr, this.profile?.maxDpr || 1)
    this.renderer.setPixelRatio(this.dpr)
    this.renderer.setSize(this.width, this.height, false)
    this.camera.aspect = this.width / this.height
    this.camera.updateProjectionMatrix()
  }

  setQuality(profile: QualityProfile) { this.profile = profile; this.currentResolution = 0 }

  render(scene: MathScene, time: number) {
    if (this.paused || scene.kind !== 'surface' || !this.renderer || !this.scene3d || !this.camera) return
    const resolution = Math.min(190, this.profile.surfaceResolution)
    if (`${scene.preset}:${scene.expression}` !== this.currentPreset || resolution !== this.currentResolution) this.rebuild(scene, resolution)
    if (this.mesh) {
      const material = this.mesh.material as import('three-modern').MeshStandardMaterial
      material.wireframe = scene.wireframe
      if (scene.autoRotate) this.mesh.rotation.y = time * Math.PI * 2
    }
    this.controls?.update()
    this.renderer.render(this.scene3d, this.camera)
  }

  pause() { this.paused = true; if (this.controls) this.controls.enabled = false }
  resume() { this.paused = false; if (this.controls) this.controls.enabled = true }

  dispose() {
    this.controls?.dispose()
    if (this.mesh) {
      this.mesh.geometry.dispose()
      const material = this.mesh.material as import('three-modern').Material
      material.dispose()
    }
    if (this.renderer) {
      this.renderer.domElement.removeEventListener('webglcontextlost', this.contextLost)
      this.renderer.domElement.removeEventListener('webglcontextrestored', this.contextRestored)
      this.renderer.dispose()
      this.renderer.domElement.remove()
    }
    this.mesh = null; this.renderer = null; this.camera = null; this.scene3d = null; this.controls = null; this.three = null
  }

  private rebuild(scene: SurfaceScene, resolution: number) {
    if (!this.three || !this.scene3d) return
    if (this.mesh) { this.scene3d.remove(this.mesh); this.mesh.geometry.dispose(); (this.mesh.material as import('three-modern').Material).dispose() }
    const geometry = new this.three.PlaneGeometry(10, 10, resolution, resolution)
    const positions = geometry.attributes.position
    for (let index = 0; index < positions.count; index += 1) {
      const x = positions.getX(index); const y = positions.getY(index)
      positions.setZ(index, sampleSurfaceScene(scene, x, y))
    }
    positions.needsUpdate = true
    geometry.computeVertexNormals()
    const accent = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim() || '#10c469'
    const material = new this.three.MeshStandardMaterial({ color: accent, roughness: .62, metalness: .06, side: this.three.DoubleSide, wireframe: scene.wireframe })
    this.mesh = new this.three.Mesh(geometry, material)
    this.mesh.rotation.x = -Math.PI / 2
    this.scene3d.add(this.mesh)
    this.currentPreset = `${scene.preset}:${scene.expression}`
    this.currentResolution = resolution
  }

  private contextLost = (event: Event) => { event.preventDefault(); this.pause(); this.renderer?.domElement.dispatchEvent(new CustomEvent('math-renderer-error', { bubbles: true, detail: 'WebGL context lost. Switching renderer is recommended.' })) }
  private contextRestored = () => { this.currentResolution = 0; this.resume() }
}
