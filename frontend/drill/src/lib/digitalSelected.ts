import { circuitFilters } from './circuitSelected'

export const digitalFilters = circuitFilters

export function digitalPracticeQuery(query: Record<string, unknown>) {
  return { ...digitalFilters(query), collection: 'digital_selected', from: 'digital-selected' }
}
