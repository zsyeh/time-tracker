export function heatmapProgress(total: number, attempted: number, mastered: number) {
  const percent = (denominator: number) => denominator
    ? `${Math.round(mastered * 1000 / denominator) / 10}%`
    : '—'
  return {
    attempted,
    unattempted: total - attempted,
    mastered,
    attemptedMasterRate: percent(attempted),
    totalMasterRate: percent(total),
  }
}
