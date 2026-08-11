import type { RuntimeCapabilities } from '../types'

interface NavigatorWithGraphics extends Navigator {
  gpu?: unknown
  deviceMemory?: number
}

export function detectCapabilities(): RuntimeCapabilities {
  const canvas = document.createElement('canvas')
  const navigatorWithGraphics = navigator as NavigatorWithGraphics
  let webgl2 = false
  let webgl1 = false
  let canvas2d = false
  try { webgl2 = Boolean(canvas.getContext('webgl2', { failIfMajorPerformanceCaveat: true })) } catch { /* unavailable */ }
  try { webgl1 = webgl2 || Boolean(canvas.getContext('webgl', { failIfMajorPerformanceCaveat: true })) } catch { /* unavailable */ }
  try { canvas2d = Boolean(canvas.getContext('2d')) } catch { /* unavailable */ }

  return {
    webgpu: Boolean(navigatorWithGraphics.gpu),
    webgl2,
    webgl1,
    canvas2d,
    reducedMotion: matchMedia('(prefers-reduced-motion: reduce)').matches,
    devicePixelRatio: Math.max(1, window.devicePixelRatio || 1),
    hardwareConcurrency: navigator.hardwareConcurrency || undefined,
    deviceMemoryGb: navigatorWithGraphics.deviceMemory,
  }
}
