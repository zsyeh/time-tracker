import { circuitFilters } from './circuitSelected'

export const analogFilters = circuitFilters

export function analogPracticeQuery(query: Record<string, unknown>) {
  return { ...analogFilters(query), collection: 'analog_selected', from: 'analog-selected' }
}
