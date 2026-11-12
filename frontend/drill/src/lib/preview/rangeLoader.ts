/** Coalesce scrollbar scrubs; obsolete batches must not delay the final viewport. */
export function createPreviewRangeLoader(options: {
  cached(offset: number): boolean
  load(offset: number, signal: AbortSignal): Promise<unknown>
  delay?: number
}) {
  let timer: ReturnType<typeof setTimeout> | undefined
  let wanted: number[] = [], disposed = false
  const active = new Map<number, AbortController>()
  function pump() {
    if (disposed || timer !== undefined) return
    for (const offset of wanted) {
      if (active.size >= 2) break
      if (options.cached(offset) || active.has(offset)) continue
      const controller = new AbortController()
      active.set(offset, controller)
      void options.load(offset, controller.signal).catch(() => {}).finally(() => {
        if (active.get(offset) === controller) {
          active.delete(offset)
          // A completed/failed batch is retried by the next range event or explicit retry.
          wanted = wanted.filter(value => value !== offset)
        }
        pump()
      })
    }
  }
  function schedule(first: number, last: number, visible = first) {
    const center = Math.floor(visible / 50) * 50
    wanted = Array.from({ length: Math.floor(last / 50) - Math.floor(first / 50) + 1 }, (_, i) => (Math.floor(first / 50) + i) * 50)
      .sort((a, b) => Math.abs(a - center) - Math.abs(b - center))
    for (const [offset, controller] of active) {
      if (!wanted.includes(offset)) { controller.abort(); active.delete(offset) }
    }
    clearTimeout(timer)
    timer = setTimeout(() => { timer = undefined; pump() }, options.delay ?? 48)
  }
  function dispose() { disposed = true; clearTimeout(timer); for (const c of active.values()) c.abort(); active.clear(); wanted = [] }
  return { schedule, dispose }
}
