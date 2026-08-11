export interface TimelineSnapshot { progress: number; playing: boolean; speed: number; direction: 1 | -1; loop: boolean }

export class Timeline {
  private frame = 0
  private last = 0
  private progress = 0
  private playing = false
  private speed = 1
  private direction: 1 | -1 = 1
  private loop = true
  private hidden = document.hidden
  private lastUiUpdate = 0

  constructor(
    private readonly onFrame: (progress: number) => void,
    private readonly onSummary: (snapshot: TimelineSnapshot) => void,
    private readonly reducedMotion = false,
  ) {
    document.addEventListener('visibilitychange', this.visibility)
  }

  play() {
    if (this.reducedMotion || this.playing) return
    this.playing = true
    this.last = performance.now()
    this.publish()
    this.frame = requestAnimationFrame(this.tick)
  }

  pause() {
    this.playing = false
    cancelAnimationFrame(this.frame)
    this.publish()
  }

  reset() { this.pause(); this.seek(0) }

  seek(progress: number) {
    this.progress = Math.max(0, Math.min(1, progress))
    this.onFrame(this.progress)
    this.publish()
  }

  setSpeed(speed: number) { this.speed = Math.max(.25, Math.min(2, speed)); this.publish() }
  reverse() { this.direction = this.direction === 1 ? -1 : 1; this.publish() }
  setLoop(loop: boolean) { this.loop = loop; this.publish() }

  dispose() { this.pause(); document.removeEventListener('visibilitychange', this.visibility) }

  private visibility = () => {
    this.hidden = document.hidden
    if (!this.hidden && this.playing) { this.last = performance.now(); this.frame = requestAnimationFrame(this.tick) }
    else cancelAnimationFrame(this.frame)
  }

  private tick = (now: number) => {
    if (!this.playing || this.hidden) return
    const delta = Math.min(50, now - this.last)
    this.last = now
    const candidate = this.progress + delta / 3200 * this.speed * this.direction
    if (this.loop) this.progress = ((candidate % 1) + 1) % 1
    else if (candidate < 0 || candidate > 1) {
      this.progress = Math.max(0, Math.min(1, candidate))
      this.onFrame(this.progress)
      this.pause()
      return
    } else this.progress = candidate
    this.onFrame(this.progress)
    if (now - this.lastUiUpdate > 180) {
      this.lastUiUpdate = now
      this.publish()
    }
    this.frame = requestAnimationFrame(this.tick)
  }

  private publish() { this.onSummary({ progress: this.progress, playing: this.playing, speed: this.speed, direction: this.direction, loop: this.loop }) }
}
