import type { Router } from 'vue-router'
import { readLocal, setLearningUser, windowOwner, writeLocal } from './foregroundTimer'
type Request = <T>(url: string, options?: RequestInit) => Promise<T>
type Place = { path: string; scroll: Record<string, number>; updated_at?: string }
type Recovery = { version: number; last_workspace: string | null; locations: Record<string, Place> }
const launch = new URL(location.href).searchParams.get('pwa_launch') === '1'
export function safeResumePath(path: string) {
  if (!path.startsWith('/') || path.startsWith('//') || path.includes('\\')) return false
  const url = new URL(path, location.origin)
  if (url.hash || [...url.searchParams.keys()].some(k => /token|password|secret|csrf|key|pwa_launch/i.test(k))) return false
  return /^\/(?:today|trends|sessions(?:\/[0-9a-f-]{36})?|issues|settings)?$/.test(url.pathname)
    || /^\/(drill|ei)\/(?:practice(?:\/[0-9a-f-]{36})?|activity|book-activity|heatmap|selected-heatmap|core-heatmap|insight|favorites|review-later|diagnostics|diagnostic-queue|cockpit|circuit-selected|signal-selected|signal-formulas|analog-selected|digital-selected|communication-selected|papers|errata|feel)$/.test(url.pathname)
}
export function isRecoveryLaunch() { return launch && (matchMedia('(display-mode: standalone)').matches || (navigator as Navigator & { standalone?: boolean }).standalone === true) }
export async function startLearningRecovery(user: string | number, workspace: string, router: Router, request: Request) {
  setLearningUser(user)
  const key = `learning.locations.v2.${user}`
  let local = readLocal<Recovery & { dirty?: boolean }>(key) || { version: 0, last_workspace: null, locations: {} }
  let stopped = false, pending = false, timer = 0, remoteReady = false, dirty = false
  let restorePlace = local.locations[workspace]
  const owner = windowOwner()
  const endpoint = '/api/learning/recovery/'
  const prefix = workspace === 'timer' ? '' : `/${workspace}`
  function currentPath() { return prefix+router.currentRoute.value.fullPath.replace(/([?&])pwa_launch=1(&|$)/, '$1').replace(/[?&]$/, '') }
  function allowed() { return !router.currentRoute.value.meta.public && !/^\/(accounts|admin|share|api)(\/|$)/.test(router.currentRoute.value.path) && router.currentRoute.value.matched.length > 0 }
  async function fetchRemote() {
    try {
      const controller = new AbortController()
      const timeout = setTimeout(() => controller.abort(), 3000)
      let remote: Recovery
      try { remote = await request<Recovery>(endpoint, { signal: controller.signal }) } finally { clearTimeout(timeout) }
      if (!Number.isInteger(remote.version) || !remote.locations || typeof remote.locations !== 'object') throw new Error('Invalid recovery response')
      remoteReady = true
      const cached = readLocal<Recovery & { dirty?: boolean }>(key)
      if (cached?.dirty && cached.version !== remote.version) writeLocal(key+'.conflict', cached)
      local = cached?.dirty && cached.version === remote.version ? { ...remote, last_workspace: cached.last_workspace, locations: { ...remote.locations, ...cached.locations }, dirty: true } : remote
      writeLocal(key, local)
    } catch { /* offline or migration not deployed: retain local positions */ }
  }
  await fetchRemote()
  if (stopped) return () => {}
  if (isRecoveryLaunch() && location.hostname === '47.95.10.128' && location.pathname === '/') {
    const url = new URL(location.href); url.searchParams.delete('pwa_launch')
    await router.replace(url.pathname+url.search)
    const target = local.last_workspace && local.locations[local.last_workspace]
    // Server validation before restoring a cached question prevents deleted or
    // out-of-workspace UUIDs from being revived from local storage.
    if (target && target.path !== '/' && remoteReady && safeResumePath(target.path)) {
      try {
        const m = target.path.match(/^\/(drill|ei)\/practice\/([0-9a-f-]{36})(?:\?|$)/)
        if (m) {
          const raw = await fetch(`/${m[1]}/api/drill/questions/${m[2]}/`, { credentials: 'same-origin', headers: { Accept: 'application/json', 'X-Learning-User-ID': String(user) } })
          if (!raw.ok) throw new Error('Unavailable question')
        }
        location.replace(target.path)
        return () => { stopped = true }
      } catch { /* keep default home; marker already consumed, no loops */ }
    }
  }
  restorePlace = local.locations[workspace]
  function scrollState() {
    return { window: Math.round(window.scrollY), right: Math.round(document.querySelector('.question-control-pane')?.scrollTop || 0), left: Math.round(document.querySelector('.question-problem-pane')?.scrollTop || 0) }
  }
  function capture(force = false) {
    if (stopped || (!force && (document.visibilityState === 'hidden' || !document.hasFocus())) || !allowed()) return
    // Re-read the user-scoped envelope so Drill cannot overwrite newer EI data.
    local = readLocal<typeof local>(key) || local
    const path = currentPath(), previous = local.locations[workspace]
    const scroll = performance.now() < restoreUntil && restorePlace?.path === path ? restorePlace.scroll : scrollState()
    if (previous?.path === path && JSON.stringify(previous.scroll) === JSON.stringify(scroll) && local.last_workspace === workspace) return
    local.last_workspace = workspace
    local.locations[workspace] = { path, scroll, updated_at: new Date().toISOString() }
    local.dirty = true; dirty = true; writeLocal(key, local)
  }
  async function sync(keepalive = false) {
    if (stopped || pending || !dirty || (!keepalive && document.visibilityState === 'hidden') || !allowed()) return
    pending = true
    const place = local.locations[workspace]
    try {
      if (!remoteReady) await fetchRemote()
      if (!remoteReady) return
      const result = await request<Recovery>(endpoint, { method: 'PUT', keepalive, body: JSON.stringify({ version: local.version, workspace, location: place, owner }) })
      const latest = readLocal<typeof local>(key)
      if (latest && latest.locations[workspace]?.updated_at === place.updated_at) {
        local = { ...result, locations: { ...result.locations, ...latest.locations }, dirty: false }; dirty = false
      } else local = { ...(latest || local), version: result.version }
      writeLocal(key, local)
    } catch (error) {
      if ((error as { status?: number }).status === 409) { remoteReady = false; await fetchRemote() }
    } finally { pending = false }
  }
  // Restore only this exact route, after data/images have settled. Stop as soon
  // as the user interacts, rather than fighting subsequent scroll gestures.
  let restoreUntil = performance.now()+4000
  const restorePath = currentPath()
  function restoreScroll() {
    if (performance.now() > restoreUntil || !restorePlace || restorePlace.path !== restorePath || currentPath() !== restorePath) return
    window.scrollTo(0, restorePlace.scroll.window || 0)
    const right = document.querySelector('.question-control-pane'), left = document.querySelector('.question-problem-pane')
    if (right) right.scrollTop = restorePlace.scroll.right || 0
    if (left) left.scrollTop = restorePlace.scroll.left || 0
  }
  const stopRestore = () => { restoreUntil = 0 }
  document.addEventListener('pointerdown', stopRestore, { passive: true })
  document.addEventListener('wheel', stopRestore, { passive: true })
  document.addEventListener('keydown', stopRestore)
  const observer = new ResizeObserver(restoreScroll)
  observer.observe(document.getElementById('app') || document.body)
  document.addEventListener('load', restoreScroll, true)
  requestAnimationFrame(restoreScroll)
  const mutations = new MutationObserver(restoreScroll)
  mutations.observe(document.getElementById('app') || document.body, { childList: true, subtree: true })
  const restoreCleanup = setTimeout(() => { observer.disconnect(); mutations.disconnect() }, 4000)
  const routeStop = router.afterEach(() => { restoreUntil = 0; capture(); void sync() })
  const onHide = () => { if (document.visibilityState === 'hidden') { capture(true); void sync(true) } else { capture(); void sync() } }
  const onPageHide = () => { capture(true); void sync(true) }
  const onOnline = () => { void sync() }
  const onShow = () => { restoreScroll(); void sync() }
  const onAccount = (event: StorageEvent) => {
    if (event.key === 'learning.identity.v2' && readLocal<string>('learning.identity.v2') !== String(user)) {
      stopped = true; location.reload()
    }
  }
  window.addEventListener('storage', onAccount)
  document.addEventListener('visibilitychange', onHide)
  window.addEventListener('pagehide', onPageHide)
  window.addEventListener('pageshow', onShow)
  window.addEventListener('online', onOnline)
  capture(); void sync()
  timer = window.setInterval(() => { capture(); void sync() }, 15000)
  return () => {
    capture(); void sync(true); stopped = true; clearInterval(timer); routeStop(); observer.disconnect(); mutations.disconnect(); clearTimeout(restoreCleanup)
    document.removeEventListener('pointerdown', stopRestore); document.removeEventListener('wheel', stopRestore); document.removeEventListener('keydown', stopRestore)
    document.removeEventListener('load', restoreScroll, true); document.removeEventListener('visibilitychange', onHide)
    window.removeEventListener('pagehide', onPageHide); window.removeEventListener('pageshow', onShow); window.removeEventListener('online', onOnline); window.removeEventListener('storage', onAccount)
  }
}
