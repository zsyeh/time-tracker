import { qualityProfiles } from './quality'
import type { QualityProfile, QualityTier } from '../types'

const tiers: QualityTier[] = ['compatibility', 'low', 'balanced', 'high']

export class PerformanceManager {
  private ema = 16.7
  private slowSince = 0
  private fastSince = 0

  constructor(private profile: QualityProfile, private readonly automatic: boolean) {}

  recordFrame(frameTime: number, now = performance.now()): QualityProfile | null {
    this.ema = this.ema * 0.92 + Math.min(100, frameTime) * 0.08
    if (!this.automatic) return null
    if (this.ema > 22) {
      if (!this.slowSince) this.slowSince = now
      this.fastSince = 0
      if (now - this.slowSince > 3000) return this.shift(-1)
    } else if (this.ema < 11) {
      if (!this.fastSince) this.fastSince = now
      this.slowSince = 0
      if (now - this.fastSince > 9000) return this.shift(1)
    } else {
      this.slowSince = 0
      this.fastSince = 0
    }
    return null
  }

  get averageFrameTime() { return this.ema }

  private shift(direction: -1 | 1): QualityProfile | null {
    const index = tiers.indexOf(this.profile.tier)
    const next = tiers[Math.max(0, Math.min(tiers.length - 1, index + direction))]
    this.slowSince = 0
    this.fastSince = 0
    if (next === this.profile.tier) return null
    this.profile = qualityProfiles[next]
    return this.profile
  }
}
