export const PREVIEW_WINDOW_TARGET = 20
export const PREVIEW_KEY_CACHE_LIMIT = 500
export type PreviewAssetGeometry = { width: number; height: number }

/** Reserve actual scan aspect ratios before network/decode; text is measured later. */
export function estimatePreviewHeight(assets: readonly PreviewAssetGeometry[] | undefined, width: number, markdown = '') {
  const available = Math.max(160, width - 32)
  const imageHeight = assets?.reduce((sum, asset) => sum + (asset.width > 0 && asset.height > 0 ? available * asset.height / asset.width : 240) + 8, 0) ?? 0
  return Math.max(144, 104 + imageHeight + (markdown && !assets?.length ? Math.min(560, 28 * Math.ceil(markdown.length / Math.max(16, Math.floor(available / 14)))) : 0))
}

/** Visible rows are never removed to satisfy a budget. Extra rows are expendable. */
export function previewRange(start: number, end: number, count: number, height: number, estimate: (index: number) => number, backward = false, target = PREVIEW_WINDOW_TARGET) {
  if (count <= 0) return []
  let first = Math.max(0, start), last = Math.min(count - 1, end)
  const limit = Math.max(target, last - first + 1)
  let before = 0, after = 0
  const beforeGoal = height * (backward ? 3 : 2), afterGoal = height * (backward ? 2 : 3)
  while (last - first + 1 < limit) {
    const canBefore = first > 0 && before < beforeGoal
    const canAfter = last < count - 1 && after < afterGoal
    if (!canBefore && !canAfter) break
    const chooseBefore = canBefore && (!canAfter || before / beforeGoal < after / afterGoal)
    if (chooseBefore) before += Math.max(1, estimate(--first))
    else after += Math.max(1, estimate(++last))
  }
  return Array.from({ length: last - first + 1 }, (_, index) => first + index)
}

export function rememberBounded<K, V>(cache: Map<K, V>, key: K, value: V, limit = PREVIEW_KEY_CACHE_LIMIT) {
  cache.delete(key); cache.set(key, value)
  while (cache.size > limit) cache.delete(cache.keys().next().value!)
}
