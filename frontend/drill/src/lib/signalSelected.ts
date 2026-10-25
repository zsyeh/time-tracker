import { circuitFilters } from './circuitSelected'

export const signalFilters = circuitFilters

export function signalPracticeQuery(query: Record<string, unknown>) {
  return { ...signalFilters(query), collection: 'signal_selected', from: 'signal-selected' }
}
