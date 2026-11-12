import { parseListContext } from './listContext'
export function activeDestination(name: unknown, query: Record<string, unknown>): string {
  const route=String(name||'')
  if (route === 'preview' || (route === 'question' && query.from === 'preview')) {
    const context = parseListContext(query.list)
    const origin = context?.returnTo.split(/[?#]/)[0].split('/')[1]
    if (origin) return origin === 'diagnostic-queue' ? 'diagnostics' : origin
    return 'practice'
  }
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
