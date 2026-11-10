/** Existing question timing API, protocol 2. No background wall-time accounting. */
export type TimerSnapshot = {
  key: string; elapsedMs: number; countdownMs: number; sequence: number; acknowledged: number;
  submissionKey: string | null; finalized: boolean; owner: string; ackOwner?: string; claimed: boolean
}
export type TimingReply = { local_base_valid?: boolean; protocol: number; timing_key: string; elapsed_ms: number; countdown_ms: number; sequence: number; owner: string; finalized: boolean }
type Request = <T>(url: string, options?: RequestInit) => Promise<T>
export let learningUserId = ''
export function setLearningUser(id: string | number) { learningUserId = String(id); writeLocal('learning.identity.v2', learningUserId) }
export function readLocal<T>(key: string): T | null {
  try { return JSON.parse(localStorage.getItem(key) || 'null') as T | null } catch { return null }
}
export function writeLocal(key: string, value: unknown) {
  try { localStorage.setItem(key, JSON.stringify(value)) } catch { /* private/quota: server still works */ }
}
// Queue at call time across question instances: the old pause reaches the
// server before the next claim, without delaying route/image rendering.
let transportQueue = Promise.resolve()
let owner = ''
export function windowOwner() {
  if (owner) return owner
  try { owner = sessionStorage.getItem('learning.window.v2') || crypto.randomUUID(); sessionStorage.setItem('learning.window.v2', owner) }
  catch { owner = crypto.randomUUID() }
  return owner
}
export class ForegroundTimer {
  state: TimerSnapshot
  status = 'syncing'
  private last = performance.now()
  private visible = false
  private savedAt = 0
  private syncedAt = 0
  private queue = Promise.resolve()
  private disposed = false
  private pauseRequested = false
  private submitting = false
  private retryAfter = 0
  readonly storageKey: string
  constructor(readonly user: string, readonly workspace: string, readonly uuid: string,
              private request: Request, private changed: () => void = () => {}) {
    this.storageKey = `learning.timer.v2.${user}.${workspace}.${uuid}`
    const saved = readLocal<TimerSnapshot>(this.storageKey)
    this.state = saved && !saved.finalized && /^[0-9a-f-]{36}$/i.test(saved.key) && Number.isFinite(saved.elapsedMs) && saved.elapsedMs >= 0 && saved.elapsedMs <= 43200000 && Number.isFinite(saved.countdownMs) && saved.countdownMs >= 0 && saved.countdownMs <= 5000 && Number.isSafeInteger(saved.sequence) ? saved : this.fresh()
    // A new window must claim its lease before counting. Refreshing the same
    // window can continue from the last local checkpoint while reconnecting.
    this.visible = document.visibilityState !== 'hidden' && this.state.claimed && this.state.owner === windowOwner()
    this.state.owner = windowOwner()
  }
  private fresh(): TimerSnapshot {
    return { key: crypto.randomUUID(), elapsedMs: 0, countdownMs: 5000, sequence: 0, acknowledged: 0,
      submissionKey: null, finalized: false, owner: windowOwner(), ackOwner: windowOwner(), claimed: false }
  }
  persist() { writeLocal(this.storageKey, this.state); this.savedAt = performance.now() }
  tick(now = performance.now()) {
    const delta = Math.max(0, now-this.last); this.last = now
    // Frozen/suspended processes do not earn a large invisible interval.
    if (this.visible && !this.state.finalized && delta <= 15000) {
      const ready = Math.min(this.state.countdownMs, delta)
      this.state.countdownMs -= ready
      this.state.elapsedMs = Math.min(43200000, this.state.elapsedMs + delta-ready)
    }
    if (now-this.savedAt >= 5000) this.persist()
    if (!this.disposed && !this.submitting && !this.state.finalized && now-this.syncedAt >= 15000 && now >= this.retryAfter && document.visibilityState !== 'hidden') {
      this.syncedAt = now
      void this.sync(this.state.claimed && this.status !== 'conflict' ? 'checkpoint' : 'claim')
    }
    this.changed()
  }
  sync(action: 'claim' | 'checkpoint' | 'pause', keepalive = false) {
    // Serialize snapshots, including the final visibility/route pause. A late
    // response cannot replace a newer local cumulative snapshot.
    const prior = this.queue
    this.queue = transportQueue.then(() => prior).then(async () => {
      if (this.state.finalized || (!this.state.claimed && action !== 'claim')) return
      this.tickWithoutSync()
      this.state.sequence += 1; this.persist()
      const sent = { ...this.state }
      try {
        const controller = new AbortController()
        const timeout = setTimeout(() => controller.abort(), 8000)
        let reply: TimingReply
        try { reply = await this.request<TimingReply>(`/api/drill/questions/${this.uuid}/timing/`, {
          method: 'POST', keepalive, signal: controller.signal, body: JSON.stringify({ protocol: 2, action, timing_key: sent.key,
            owner: sent.owner, resume_owner: sent.ackOwner || sent.owner, base_elapsed_ms: sent.acknowledged, sequence: sent.sequence, elapsed_ms: Math.floor(sent.elapsedMs), countdown_ms: Math.ceil(sent.countdownMs) }),
        }) } finally { clearTimeout(timeout) }
        if (this.state.finalized) return
        if (reply.protocol !== 2) throw new Error('Foreground recovery requires the compatible server migration.')
        if (action === 'claim') {
          const compatible = reply.timing_key === sent.key && reply.local_base_valid !== false && reply.elapsed_ms >= sent.acknowledged
          if (!compatible && sent.elapsedMs > sent.acknowledged) {
            // Never silently add an offline delta to a different device/round.
            writeLocal(this.storageKey+'.conflict', sent)
          }
          const pending = compatible ? Math.max(0, this.state.elapsedMs-sent.elapsedMs) : 0
          const ownPending = compatible && reply.local_base_valid !== false && reply.owner === sent.owner
          this.state.key = reply.timing_key
          this.state.elapsedMs = ownPending ? Math.max(this.state.elapsedMs, reply.elapsed_ms) : reply.elapsed_ms+pending
          this.state.countdownMs = ownPending ? Math.min(this.state.countdownMs, reply.countdown_ms) : reply.countdown_ms
          this.state.sequence = Math.max(this.state.sequence, reply.sequence)
          this.state.claimed = true
          this.visible = !this.disposed && document.visibilityState !== 'hidden'
          this.last = performance.now()
        }
        if (reply.finalized) { this.state.elapsedMs = reply.elapsed_ms; this.visible = false }
        this.state.sequence = Math.max(this.state.sequence, reply.sequence)
        this.state.ackOwner = reply.owner
        this.state.acknowledged = reply.elapsed_ms
        this.state.finalized = reply.finalized
        this.status = 'saved'; this.persist(); this.changed()
      } catch (error) {
        const code = (error as { status?: number }).status
        this.status = code === 409 || code === 400 || code === 404 ? 'conflict' : 'offline'
        if (code === 409 || code === 400 || code === 404) {
          this.visible = false; this.state.claimed = false
          this.retryAfter = performance.now()+45000
        }
        this.persist(); this.changed()
      }
    })
    transportQueue = this.queue.catch(() => {})
    return this.queue
  }
  private tickWithoutSync() {
    const now = performance.now(), delta = Math.max(0, now-this.last); this.last = now
    if (this.visible && !this.state.finalized && delta <= 15000) {
      const ready = Math.min(this.state.countdownMs, delta); this.state.countdownMs -= ready
      this.state.elapsedMs = Math.min(43200000, this.state.elapsedMs+delta-ready)
    }
  }
  activate() { this.pauseRequested = false; this.last = performance.now(); return this.sync('claim') }
  pause() { if (this.pauseRequested) return this.queue; this.pauseRequested = true; this.tickWithoutSync(); this.visible = false; this.persist(); return this.sync('pause', true) }
  snapshot() {
    this.tickWithoutSync(); this.submitting = true; this.visible = false; this.state.sequence += 1; this.persist()
    return { timing_key: this.state.key, timing_protocol: 2, timing_owner: this.state.owner,
      timing_sequence: this.state.sequence, timing_elapsed_ms: Math.floor(this.state.elapsedMs) }
  }
  submissionKey() { if (!this.state.submissionKey) this.state.submissionKey = crypto.randomUUID(); this.persist(); return this.state.submissionKey }
  resumeAfterFailure() { this.submitting = false; this.last = performance.now(); this.visible = this.state.claimed && document.visibilityState !== 'hidden' }
  finish() { this.visible = false; this.state.finalized = true; this.state.submissionKey = null; this.persist() }
  dispose() { this.disposed = true; return this.pause() }
}
