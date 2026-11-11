/** Existing question timing API, protocol 2. No background wall-time accounting. */
export type TimerSnapshot = {
  key: string; elapsedMs: number; countdownMs: number; sequence: number; acknowledged: number;
  submissionKey: string | null; pendingAttempt?: Record<string, unknown>; finalized: boolean; owner: string; ackOwner?: string; claimed: boolean
}
export type TimingReply = { local_base_valid?: boolean; protocol: number; timing_key: string; elapsed_ms: number; countdown_ms: number; sequence: number; owner: string; finalized: boolean }
export type TimingIssue = {
  reason: string; can_reclaim: boolean; lease_retry_after?: number;
  lease_live?: boolean; owner_matches?: boolean; active_matches?: boolean
}
export type TimingSyncResult = { status: 'success'; finalized: boolean } | { status: 'recoverable' | 'conflict'; issue: TimingIssue }
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
  // sessionStorage is cloned when Safari duplicates a tab. Ownership must belong
  // to this document, never to a copied tab/sessionStorage identifier.
  if (!owner) owner = crypto.randomUUID()
  return owner
}

export class ForegroundTimer {
  state: TimerSnapshot
  status = 'syncing'
  issue: TimingIssue | null = null
  private last = performance.now()
  private visible = false
  private savedAt = 0
  private syncedAt = 0
  private queue: Promise<TimingSyncResult> = Promise.resolve({ status: 'success', finalized: false })
  private disposed = false
  private pauseRequested = false
  private submitting = false
  private retryAfter = 0
  readonly storageKey: string
  constructor(readonly user: string, readonly workspace: string, readonly uuid: string,
              private request: Request, private changed: () => void = () => {}) {
    this.storageKey = `learning.timer.v2.${user}.${workspace}.${uuid}`
    const saved = readLocal<TimerSnapshot>(this.storageKey)
    this.state = saved && (!saved.finalized || Boolean(saved.pendingAttempt && saved.submissionKey)) && /^[0-9a-f-]{36}$/i.test(saved.key) && Number.isFinite(saved.elapsedMs) && saved.elapsedMs >= 0 && saved.elapsedMs <= 43200000 && Number.isFinite(saved.countdownMs) && saved.countdownMs >= 0 && saved.countdownMs <= 5000 && Number.isSafeInteger(saved.sequence) ? saved : this.fresh()
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
  sync(action: 'claim' | 'checkpoint' | 'pause', keepalive = false): Promise<TimingSyncResult> {
    // Serialize snapshots, including the final visibility/route pause. A late
    // response cannot replace a newer local cumulative snapshot.
    const prior = this.queue
    this.queue = transportQueue.then(() => prior).then(async (): Promise<TimingSyncResult> => {
      if (this.state.finalized) return { status: 'success', finalized: true }
      if (!this.state.claimed && action !== 'claim') return { status: this.issue?.can_reclaim === false ? 'conflict' : 'recoverable', issue: this.issue || { reason: 'claim_required', can_reclaim: true } }
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
        if (this.state.finalized) return { status: 'success', finalized: true }
        if (reply.protocol !== 2) throw Object.assign(new Error('Incompatible timing protocol'), { status: 400, body: { reason: 'incompatible_protocol' } })
        if (action !== 'claim' && reply.owner !== sent.owner) {
          throw Object.assign(new Error('Timer owner changed'), { status: 409, body: { reason: 'owner_mismatch', can_reclaim: false, owner_matches: false } })
        }
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
        if (reply.finalized) {
          if(this.state.elapsedMs>reply.elapsed_ms)writeLocal(this.storageKey+'.conflict',{...this.state})
          this.state.elapsedMs = reply.elapsed_ms; this.visible = false
        }
        this.state.sequence = Math.max(this.state.sequence, reply.sequence)
        this.state.ackOwner = reply.owner
        this.state.acknowledged = reply.elapsed_ms
        this.state.finalized = reply.finalized
        this.status = 'saved'; this.issue = null; this.persist(); this.changed()
        return { status: 'success', finalized: reply.finalized }
      } catch (error) {
        return this.recordFailure(error)
      }
    })
    transportQueue = this.queue.then(() => {}, () => {})
    return this.queue
  }
  recordFailure(error: unknown): TimingSyncResult {
    const failure = (error&&typeof error==='object'?error:{}) as { status?: number; body?: Record<string, unknown> }
    const code = failure.status
    const body = failure.body || {}
    const permittedReasons = ['owner_mismatch', 'lease_expired', 'stale_sequence', 'active_timer_mismatch', 'timing_round_missing', 'timing_finalized', 'claim_required', 'incompatible_protocol']
    const reason = typeof body.reason === 'string' && permittedReasons.includes(body.reason)
      ? body.reason : code === 409 ? 'ownership_conflict' : code === 400 || code === 404 ? 'timing_unavailable' : 'network_unavailable'
    const conflict = code === 409 || code === 400 || code === 404
    this.issue = { reason, can_reclaim: body.can_reclaim === true || (code === 409 && ['lease_expired', 'stale_sequence', 'active_timer_mismatch', 'timing_round_missing', 'timing_finalized'].includes(reason) && body.can_reclaim !== false) }
    for (const field of ['lease_live', 'owner_matches', 'active_matches'] as const) {
      if (typeof body[field] === 'boolean') this.issue[field] = body[field]
    }
    if (typeof body.lease_retry_after === 'number' && Number.isFinite(body.lease_retry_after)) this.issue.lease_retry_after = Math.max(0, Math.min(45, body.lease_retry_after))
    this.status = conflict ? 'conflict' : 'offline'
    if (conflict) {
      this.visible = false; this.state.claimed = false
      this.retryAfter = performance.now() + (this.issue.lease_retry_after ?? 45) * 1000
    }
    this.persist(); this.changed()
    return { status: conflict && !this.issue.can_reclaim ? 'conflict' : 'recoverable', issue: this.issue }
  }
  async prepareSubmission(): Promise<TimingSyncResult> {
    const first = await this.sync(this.state.claimed ? 'checkpoint' : 'claim')
    if (first.status === 'success' || first.status === 'conflict') return first
    // A network failure is not proof that a lease may be transferred. Leave the
    // snapshot intact and let the user reconnect or explicitly omit duration.
    if (!first.issue.can_reclaim) return first
    return this.sync('claim')
  }
  async reconnect(): Promise<TimingSyncResult> {
    const result = await this.activate()
    if (result.status !== 'success' || !result.finalized || this.state.pendingAttempt) return result
    // An acknowledged/completed round is immutable. A user-requested reconnect
    // starts a fresh round, preserving its previous snapshot and current draft.
    const previous = this.state
    writeLocal(this.storageKey + '.previous', previous)
    this.state = this.fresh()
    const draft = readLocal<Record<string, unknown>>(this.storageKey + '.draft')
    if (draft?.key === previous.key) writeLocal(this.storageKey + '.draft', { ...draft, key: this.state.key })
    this.visible = false; this.submitting = false; this.retryAfter = 0
    this.persist(); this.changed()
    return this.activate()
  }
  rememberAttempt(body: Record<string, unknown>) { this.state.pendingAttempt = { ...body }; this.persist(); this.changed() }
  clearPreparedAttempt() { delete this.state.pendingAttempt; this.persist(); this.changed() }
  archiveOmittedRound() { writeLocal(this.storageKey + '.omitted', { ...this.state }) }
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
  finish() { this.visible = false; this.state.finalized = true; this.state.submissionKey = null; delete this.state.pendingAttempt; this.persist(); this.changed() }
  dispose() { this.disposed = true; return this.pause() }
}
