export function activeDestination(name: unknown, query: Record<string, unknown>): string {
  const route=String(name||'')
  if(route.startsWith('paper'))return 'papers'
  if(route==='diagnostic-queue')return 'diagnostics'
  if(route!=='question')return route
  const from=String(query.from||'')
  if(['heatmap','selected-heatmap','core-heatmap','insight','diagnostics','cockpit','circuit-selected','signal-selected','analog-selected','digital-selected','communication-selected'].includes(from))return from
  const collection=String(query.collection||'')
  const selected=collection.replace('_selected','-selected')
  if(['circuit-selected','signal-selected','analog-selected','digital-selected','communication-selected'].includes(selected))return selected
  if(from==='collection')return collection==='review_later'?'review-later':'favorites'
  return 'practice'
}
