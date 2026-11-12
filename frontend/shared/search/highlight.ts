/** API highlight offsets are Unicode codepoints, never JavaScript UTF-16 units. */
export function highlightCodepoints(text: string, highlights: Array<[number, number]> = []) {
  const points = Array.from(text)
  const ranges = highlights.filter((range) => Array.isArray(range) && Number.isInteger(range[0]) && Number.isInteger(range[1]))
    .map(([start, end]) => [Math.max(0, start), Math.min(points.length, end)] as [number, number])
    .filter(([start, end]) => end > start).sort(([a], [b]) => a - b)
  const merged: Array<[number, number]> = []
  for (const [start, end] of ranges) {
    const last = merged.at(-1)
    if (last && start <= last[1]) last[1] = Math.max(last[1], end)
    else merged.push([start, end])
  }
  const output: Array<{ text: string; match: boolean }> = []
  let cursor = 0
  for (const [start, end] of merged) {
    if (start > cursor) output.push({ text: points.slice(cursor, start).join(''), match: false })
    output.push({ text: points.slice(start, end).join(''), match: true })
    cursor = end
  }
  if (cursor < points.length) output.push({ text: points.slice(cursor).join(''), match: false })
  return output.length ? output : [{ text, match: false }]
}
