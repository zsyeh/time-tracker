import { circuitFilters } from './circuitSelected'

export const communicationFilters = circuitFilters

export function communicationPracticeQuery(query: Record<string, unknown>) {
  return { ...communicationFilters(query), collection: 'communication_selected', from: 'communication-selected' }
}
