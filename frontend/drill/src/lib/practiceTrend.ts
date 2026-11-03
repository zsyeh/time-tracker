export const practiceTrendStoragePulse = 'practice.trend.updated.v1'
export const practiceTrendEvent = 'practice-trend-changed'
export const practiceTrendChannel = 'practice-trend-sync-v1'

export function notifyPracticeTrendChanged() {
  const stamp = `${Date.now()}-${Math.random()}`
  window.dispatchEvent(new CustomEvent(practiceTrendEvent, { detail: stamp }))
  try { localStorage.setItem(practiceTrendStoragePulse, stamp) } catch { /* storage may be disabled */ }
  if ('BroadcastChannel' in window) {
    const channel = new BroadcastChannel(practiceTrendChannel)
    channel.postMessage(stamp)
    channel.close()
  }
}
