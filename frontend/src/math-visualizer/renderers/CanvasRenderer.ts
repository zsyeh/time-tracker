import {
  determinant, eigenDirections, evaluateComplex, fourierCoefficient, interpolateMatrix,
  laplaceSignal, numericalLaplace, sampleSurfaceScene, signalValue, transform,
} from '../core/numerics'
import type {
  ComplexScene, FourierScene, LaplaceScene, LinearScene, MathRenderer, MathScene,
  QualityProfile, RendererCapabilities, SurfaceScene, Vec2,
} from '../types'

const TAU = Math.PI * 2

function hslToRgb(hue: number, saturation: number, lightness: number): [number, number, number] {
  const chroma = (1 - Math.abs(2 * lightness - 1)) * saturation
  const sector = ((hue % 1) + 1) % 1 * 6
  const second = chroma * (1 - Math.abs(sector % 2 - 1))
  const [r, g, b] = sector < 1 ? [chroma, second, 0] : sector < 2 ? [second, chroma, 0] : sector < 3 ? [0, chroma, second] : sector < 4 ? [0, second, chroma] : sector < 5 ? [second, 0, chroma] : [chroma, 0, second]
  const match = lightness - chroma / 2
  return [Math.round((r + match) * 255), Math.round((g + match) * 255), Math.round((b + match) * 255)]
}

export class CanvasRenderer implements MathRenderer {
  readonly id = 'canvas' as const
  readonly capabilities: RendererCapabilities = { supports3D: true, supportsComplexGpu: false, supportsInstancing: false, supportsWebGPU: false }
  private canvas!: HTMLCanvasElement
  private context!: CanvasRenderingContext2D
  private container!: HTMLElement
  private width = 1
  private height = 1
  private dpr = 1
  private profile!: QualityProfile
  private scene: MathScene | null = null
  private time = 1
  private accent = '#10c469'
  private paused = false
  private dragging = false
  private dragPoint: Vec2 | null = null
  private rotation = -.65
  private domainCache: { key: string; canvas: HTMLCanvasElement } | null = null

  async init(container: HTMLElement) {
    this.container = container
    this.canvas = document.createElement('canvas')
    this.canvas.className = 'math-viewport-canvas'
    this.canvas.setAttribute('aria-label', 'Interactive mathematical visualization')
    const context = this.canvas.getContext('2d', { alpha: false })
    if (!context) throw new Error('Canvas2D is unavailable.')
    this.context = context
    container.replaceChildren(this.canvas)
    this.canvas.addEventListener('pointerdown', this.pointerDown)
    this.canvas.addEventListener('pointermove', this.pointerMove)
    this.canvas.addEventListener('pointerup', this.pointerUp)
    this.canvas.addEventListener('pointercancel', this.pointerUp)
    this.canvas.addEventListener('wheel', this.wheel, { passive: false })
  }

  resize(width: number, height: number, dpr: number) {
    this.width = Math.max(1, width)
    this.height = Math.max(1, height)
    this.dpr = Math.max(1, Math.min(dpr, this.profile?.maxDpr || 1))
    this.canvas.width = Math.round(this.width * this.dpr)
    this.canvas.height = Math.round(this.height * this.dpr)
    this.canvas.style.width = `${this.width}px`
    this.canvas.style.height = `${this.height}px`
    this.context.setTransform(this.dpr, 0, 0, this.dpr, 0, 0)
    this.draw()
  }

  setQuality(profile: QualityProfile) { this.profile = profile; this.draw() }
  render(scene: MathScene, time: number) { this.scene = scene; this.time = time; this.accent = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim() || '#10c469'; this.draw() }
  pause() { this.paused = true }
  resume() { this.paused = false; this.draw() }

  dispose() {
    this.canvas?.removeEventListener('pointerdown', this.pointerDown)
    this.canvas?.removeEventListener('pointermove', this.pointerMove)
    this.canvas?.removeEventListener('pointerup', this.pointerUp)
    this.canvas?.removeEventListener('pointercancel', this.pointerUp)
    this.canvas?.removeEventListener('wheel', this.wheel)
    this.canvas?.remove()
    this.scene = null
    this.domainCache = null
  }

  private draw() {
    if (this.paused || !this.scene || !this.context || !this.profile) return
    this.context.save()
    this.context.setTransform(this.dpr, 0, 0, this.dpr, 0, 0)
    this.context.fillStyle = '#090d11'
    this.context.fillRect(0, 0, this.width, this.height)
    switch (this.scene.kind) {
      case 'linear': this.drawLinear(this.scene); break
      case 'complex': this.drawComplex(this.scene); break
      case 'fourier': this.drawFourier(this.scene); break
      case 'laplace': this.drawLaplace(this.scene); break
      case 'surface': this.drawSurface(this.scene); break
    }
    this.context.restore()
  }

  private drawLinear(scene: LinearScene) {
    const ctx = this.context
    const matrix = interpolateMatrix(scene.matrix, this.time)
    const scale = Math.min(this.width, this.height) / 12
    const center: Vec2 = [this.width / 2, this.height / 2]
    const point = ([x, y]: Vec2): Vec2 => [center[0] + x * scale, center[1] - y * scale]
    const line = (from: Vec2, to: Vec2, color: string, width = 1) => { const a = point(from); const b = point(to); ctx.beginPath(); ctx.moveTo(...a); ctx.lineTo(...b); ctx.strokeStyle = color; ctx.lineWidth = width; ctx.stroke() }

    if (scene.showGrid) {
      for (let value = -7; value <= 7; value += 1) {
        line(transform(matrix, [value, -7]), transform(matrix, [value, 7]), value === 0 ? '#65717b' : '#273038', value === 0 ? 1.5 : 1)
        line(transform(matrix, [-7, value]), transform(matrix, [7, value]), value === 0 ? '#65717b' : '#273038', value === 0 ? 1.5 : 1)
      }
    }
    if (scene.showSquare) {
      const square: Vec2[] = [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]
      ctx.beginPath()
      square.map((item) => point(transform(matrix, item))).forEach((item, index) => index ? ctx.lineTo(...item) : ctx.moveTo(...item))
      ctx.fillStyle = `${this.accent}26`; ctx.fill(); ctx.strokeStyle = this.accent; ctx.lineWidth = 2; ctx.stroke()
    }
    this.drawArrow(point([0, 0]), point(transform(matrix, [1, 0])), '#66b7ff', 'Ae₁')
    this.drawArrow(point([0, 0]), point(transform(matrix, [0, 1])), '#ffb454', 'Ae₂')
    this.drawArrow(point([0, 0]), point(transform(matrix, scene.vector)), this.accent, 'Av')
    if (scene.showEigenvectors) {
      for (const eigen of eigenDirections(scene.matrix)) {
        line([-6 * eigen.vector[0], -6 * eigen.vector[1]], [6 * eigen.vector[0], 6 * eigen.vector[1]], '#df76ff80', 1.5)
      }
    }
    this.label(18, 24, `A(t)  det ${determinant(matrix).toFixed(3)}`, '#afb7c0')
    this.label(18, 43, determinant(scene.matrix) < 0 ? 'ORIENTATION FLIP' : 'ORIENTATION PRESERVED', determinant(scene.matrix) < 0 ? '#ff7887' : this.accent, 8)
  }

  private drawComplex(scene: ComplexScene) {
    const ctx = this.context
    const gap = 18
    const planeWidth = (this.width - gap * 3) / 2
    const top = 42
    const planeHeight = this.height - top - 18
    const leftX = gap
    const rightX = gap * 2 + planeWidth
    const pointValue = this.dragPoint || scene.point
    const mapped = evaluateComplex(scene.preset, { re: pointValue[0], im: pointValue[1] })
    if (scene.domainColoring) this.domainColor(scene, rightX, top, planeWidth, planeHeight)
    this.drawComplexPlane(leftX, top, planeWidth, planeHeight, 'z-plane', scene.showGrid)
    this.drawComplexPlane(rightX, top, planeWidth, planeHeight, 'w-plane', scene.showGrid && !scene.domainColoring)
    const toPixel = (origin: number, value: Vec2): Vec2 => [origin + planeWidth / 2 + value[0] * planeWidth / 8, top + planeHeight / 2 - value[1] * planeHeight / 8]
    const zPixel = toPixel(leftX, pointValue)
    this.dot(zPixel, this.accent, 'z')
    if (mapped && Number.isFinite(mapped.re) && Number.isFinite(mapped.im)) this.dot(toPixel(rightX, [Math.max(-4, Math.min(4, mapped.re)), Math.max(-4, Math.min(4, mapped.im))]), '#ffb454', 'f(z)')
    else this.label(rightX + 12, top + 25, 'SINGULAR / OUTSIDE FINITE PLANE', '#ff7887', 8)
    this.label(18, 24, `${scene.expression}   z=${pointValue[0].toFixed(2)}${pointValue[1] < 0 ? '' : '+'}${pointValue[1].toFixed(2)}i`, '#c1c7ce')
    ctx.strokeStyle = '#252c34'; ctx.strokeRect(leftX, top, planeWidth, planeHeight); ctx.strokeRect(rightX, top, planeWidth, planeHeight)
  }

  private domainColor(scene: ComplexScene, x: number, y: number, width: number, height: number) {
    const resolution = Math.max(80, Math.min(this.profile.complexResolution, 320, Math.round(width)))
    const rows = Math.max(60, Math.round(resolution * height / width))
    const key = `${scene.preset}:${resolution}:${rows}`
    if (this.domainCache?.key === key) {
      this.context.save(); this.context.globalAlpha = .82; this.context.drawImage(this.domainCache.canvas, x, y, width, height); this.context.restore()
      return
    }
    const offscreen = document.createElement('canvas')
    offscreen.width = resolution; offscreen.height = rows
    const offctx = offscreen.getContext('2d')!
    const image = offctx.createImageData(resolution, rows)
    for (let py = 0; py < rows; py += 1) for (let px = 0; px < resolution; px += 1) {
      const z = { re: (px / (resolution - 1) - .5) * 8, im: (.5 - py / (rows - 1)) * 8 }
      const value = evaluateComplex(scene.preset, z)
      const index = (py * resolution + px) * 4
      if (!value || !Number.isFinite(value.re) || !Number.isFinite(value.im)) { image.data[index + 3] = 255; continue }
      const magnitude = Math.hypot(value.re, value.im)
      const hue = Math.atan2(value.im, value.re) / TAU + .5
      const contour = .5 + .08 * Math.cos(Math.log1p(magnitude) * Math.PI * 4)
      const [red, green, blue] = hslToRgb(hue, .72, Math.min(.72, .24 + .34 * (1 - Math.exp(-magnitude)) + contour * .12))
      image.data[index] = red; image.data[index + 1] = green; image.data[index + 2] = blue; image.data[index + 3] = 255
    }
    offctx.putImageData(image, 0, 0)
    this.domainCache = { key, canvas: offscreen }
    this.context.save(); this.context.globalAlpha = .82; this.context.drawImage(offscreen, x, y, width, height); this.context.restore()
  }

  private drawComplexPlane(x: number, y: number, width: number, height: number, title: string, grid: boolean) {
    const ctx = this.context
    if (grid) {
      ctx.strokeStyle = '#29313a'; ctx.lineWidth = 1
      for (let index = -4; index <= 4; index += 1) {
        const px = x + width / 2 + index * width / 8; const py = y + height / 2 + index * height / 8
        ctx.beginPath(); ctx.moveTo(px, y); ctx.lineTo(px, y + height); ctx.stroke()
        ctx.beginPath(); ctx.moveTo(x, py); ctx.lineTo(x + width, py); ctx.stroke()
      }
    }
    ctx.strokeStyle = '#8a949f'; ctx.beginPath(); ctx.moveTo(x, y + height / 2); ctx.lineTo(x + width, y + height / 2); ctx.stroke(); ctx.beginPath(); ctx.moveTo(x + width / 2, y); ctx.lineTo(x + width / 2, y + height); ctx.stroke()
    this.label(x + 8, y + 16, title.toUpperCase(), '#d5dae0', 8)
  }

  private drawFourier(scene: FourierScene) {
    const ctx = this.context
    const topHeight = this.height * .42
    const leftWidth = this.width * .54
    this.label(18, 24, `FOURIER · ω = ${scene.omega.toFixed(2)}`, '#d0d5db')
    this.label(18, 43, 'TIME DOMAIN', this.accent, 8)
    ctx.beginPath()
    for (let index = 0; index <= 420; index += 1) {
      const t = index / 420; const x = 18 + t * (this.width - 36); const y = 72 + topHeight / 2 - signalValue(scene.preset, t) * topHeight * .32
      index ? ctx.lineTo(x, y) : ctx.moveTo(x, y)
    }
    ctx.strokeStyle = this.accent; ctx.lineWidth = 1.7; ctx.stroke()
    if (scene.showWrapping) {
      const center: Vec2 = [leftWidth * .5, topHeight + (this.height - topHeight) * .53]
      const scale = Math.min(leftWidth, this.height - topHeight) * .22
      ctx.strokeStyle = '#303842'; ctx.beginPath(); ctx.arc(...center, scale, 0, TAU); ctx.stroke()
      ctx.beginPath()
      for (let index = 0; index <= 320; index += 1) {
        const t = index / 320; const radius = signalValue(scene.preset, t) * scale; const angle = TAU * scene.omega * t
        const p: Vec2 = [center[0] + Math.cos(angle) * radius, center[1] + Math.sin(angle) * radius]
        index ? ctx.lineTo(...p) : ctx.moveTo(...p)
      }
      ctx.strokeStyle = '#64b5ff'; ctx.stroke(); this.label(18, topHeight + 30, 'COMPLEX WRAPPING', '#64b5ff', 8)
      const coefficient = fourierCoefficient(scene.preset, scene.omega, Math.min(this.profile.curveSamples, 1600))
      this.dot([center[0] + coefficient.re * scale * 2, center[1] - coefficient.im * scale * 2], '#ffb454', '∫')
    }
    if (scene.showSpectrum) {
      const originX = leftWidth + 24; const originY = this.height - 45; const available = this.width - originX - 22
      for (let frequency = 0; frequency <= 12; frequency += 1) {
        const magnitude = scene.spectrum[frequency] ?? 0
        const x = originX + frequency / 12 * available
        ctx.strokeStyle = frequency === Math.round(scene.omega) ? '#ffb454' : this.accent; ctx.lineWidth = 3
        ctx.beginPath(); ctx.moveTo(x, originY); ctx.lineTo(x, originY - magnitude * (this.height - topHeight) * 1.25); ctx.stroke()
      }
      this.label(originX, topHeight + 30, 'FREQUENCY RESPONSE', this.accent, 8)
    }
  }

  private drawLaplace(scene: LaplaceScene) {
    const ctx = this.context
    const result = numericalLaplace(scene.preset, scene.sigma, scene.omega, 12, Math.min(3000, this.profile.curveSamples * 2))
    this.label(18, 24, `LAPLACE · s = ${scene.sigma.toFixed(2)} ${scene.omega < 0 ? '−' : '+'} ${Math.abs(scene.omega).toFixed(2)}i`, '#d0d5db')
    const graphTop = 58; const graphHeight = this.height * .34
    ctx.beginPath()
    for (let index = 0; index <= 360; index += 1) {
      const t = index / 45; const x = 18 + index / 360 * (this.width - 36); const weighted = laplaceSignal(scene.preset, t) * Math.exp(-scene.sigma * t); const y = graphTop + graphHeight / 2 - weighted * Math.cos(scene.omega * t) * graphHeight * .32
      index ? ctx.lineTo(x, y) : ctx.moveTo(x, y)
    }
    ctx.strokeStyle = this.accent; ctx.lineWidth = 1.6; ctx.stroke(); this.label(18, graphTop + 12, 'e⁻ˢᵗ WEIGHTED SIGNAL', this.accent, 8)
    const cx = this.width / 2; const cy = graphTop + graphHeight + (this.height - graphTop - graphHeight) / 2
    const scale = Math.min(this.width, this.height) * .09
    ctx.strokeStyle = '#48515b'; ctx.beginPath(); ctx.moveTo(18, cy); ctx.lineTo(this.width - 18, cy); ctx.stroke(); ctx.beginPath(); ctx.moveTo(cx, graphTop + graphHeight + 14); ctx.lineTo(cx, this.height - 18); ctx.stroke()
    this.dot([cx + scene.sigma * scale, cy - scene.omega * scale], '#ffb454', 's')
    this.drawArrow([cx, cy], [cx + result.re * scale, cy - result.im * scale], this.accent, 'F(s)')
    this.label(18, this.height - 22, `F(s) ≈ ${result.re.toFixed(4)} ${result.im < 0 ? '−' : '+'} ${Math.abs(result.im).toFixed(4)}i`, '#c8cdd3', 9)
  }

  private drawSurface(scene: SurfaceScene) {
    const ctx = this.context
    const resolution = Math.max(18, Math.min(52, Math.round(this.profile.surfaceResolution / 2)))
    const angle = this.rotation + (scene.autoRotate ? this.time * TAU : 0)
    const cos = Math.cos(angle); const sin = Math.sin(angle); const tilt = .56
    const project = (x: number, y: number, z: number): Vec2 => {
      const rx = x * cos - y * sin; const ry = x * sin + y * cos
      const scale = Math.min(this.width, this.height) * .09
      return [this.width / 2 + rx * scale, this.height * .55 + (ry * tilt - z) * scale]
    }
    const range = 4
    for (let row = 0; row <= resolution; row += 1) {
      const y = -range + row / resolution * range * 2
      ctx.beginPath()
      for (let column = 0; column <= resolution; column += 1) {
        const x = -range + column / resolution * range * 2; const p = project(x, y, sampleSurfaceScene(scene, x, y))
        column ? ctx.lineTo(...p) : ctx.moveTo(...p)
      }
      ctx.strokeStyle = row % 4 ? `${this.accent}50` : this.accent; ctx.lineWidth = row % 4 ? .7 : 1.2; ctx.stroke()
    }
    for (let column = 0; column <= resolution; column += 1) {
      const x = -range + column / resolution * range * 2
      ctx.beginPath()
      for (let row = 0; row <= resolution; row += 1) {
        const y = -range + row / resolution * range * 2; const p = project(x, y, sampleSurfaceScene(scene, x, y))
        row ? ctx.lineTo(...p) : ctx.moveTo(...p)
      }
      ctx.strokeStyle = `${this.accent}38`; ctx.lineWidth = .65; ctx.stroke()
    }
    this.label(18, 24, `3D SURFACE · ${scene.expression}`, '#d0d5db')
    this.label(18, 43, `CPU PROJECTION · ${resolution} × ${resolution}`, this.accent, 8)
  }

  private label(x: number, y: number, text: string, color: string, size = 10) { this.context.fillStyle = color; this.context.font = `650 ${size}px ui-monospace, monospace`; this.context.fillText(text, x, y) }
  private dot(point: Vec2, color: string, label: string) { this.context.beginPath(); this.context.arc(point[0], point[1], 5, 0, TAU); this.context.fillStyle = color; this.context.fill(); this.label(point[0] + 9, point[1] - 8, label, color, 9) }
  private drawArrow(from: Vec2, to: Vec2, color: string, label: string) { const angle = Math.atan2(to[1] - from[1], to[0] - from[0]); this.context.beginPath(); this.context.moveTo(...from); this.context.lineTo(...to); this.context.lineTo(to[0] - 9 * Math.cos(angle - .45), to[1] - 9 * Math.sin(angle - .45)); this.context.moveTo(...to); this.context.lineTo(to[0] - 9 * Math.cos(angle + .45), to[1] - 9 * Math.sin(angle + .45)); this.context.strokeStyle = color; this.context.lineWidth = 2; this.context.stroke(); this.label(to[0] + 7, to[1] - 6, label, color, 9) }

  private pointerDown = (event: PointerEvent) => { this.dragging = true; this.canvas.setPointerCapture(event.pointerId); this.updatePointer(event) }
  private pointerMove = (event: PointerEvent) => { if (this.dragging) this.updatePointer(event) }
  private pointerUp = (event: PointerEvent) => { this.dragging = false; if (this.canvas.hasPointerCapture(event.pointerId)) this.canvas.releasePointerCapture(event.pointerId) }
  private wheel = (event: WheelEvent) => { if (this.scene?.kind !== 'surface') return; event.preventDefault(); this.rotation += Math.sign(event.deltaY) * .08; this.draw() }

  private updatePointer(event: PointerEvent) {
    if (!this.scene) return
    const bounds = this.canvas.getBoundingClientRect()
    if (this.scene.kind === 'complex') {
      const gap = 18; const planeWidth = (this.width - gap * 3) / 2; const top = 42; const planeHeight = this.height - top - 18
      const x = event.clientX - bounds.left; const y = event.clientY - bounds.top
      if (x >= gap && x <= gap + planeWidth && y >= top && y <= top + planeHeight) {
        this.dragPoint = [(x - gap - planeWidth / 2) * 8 / planeWidth, (top + planeHeight / 2 - y) * 8 / planeHeight]
        this.container.dispatchEvent(new CustomEvent('math-point-change', { detail: this.dragPoint }))
      }
    } else if (this.scene.kind === 'surface') {
      this.rotation += event.movementX * .008
    }
    this.draw()
  }
}
