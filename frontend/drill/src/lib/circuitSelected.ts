export const circuitFilterKeys = ['bucket', 'tier', 'kind', 'material', 'combined', 'state'] as const

export function circuitFilters(query: Record<string, unknown>): Record<string, string> {
  return Object.fromEntries(circuitFilterKeys
    .filter((key) => typeof query[key] === 'string' && query[key] !== '')
    .map((key) => [key, String(query[key])]))
}

export function circuitPracticeQuery(query: Record<string, unknown>) {
  return { ...circuitFilters(query), collection: 'circuit_selected', from: 'circuit-selected' }
}
