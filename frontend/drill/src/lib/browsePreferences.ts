import { computed } from 'vue'
import { useAccountPreferences } from '../../../shared/preferences/store'
import { browseFilterKeys, validPreference, type BrowseFilters } from '../../../shared/preferences/schema'
import { runtimeWorkspace } from './runtimePath'

/** Account defaults for fresh navigation; an explicit URL always owns its list. */
export function useBrowsePreferences(workspace: 'drill' | 'ei' = runtimeWorkspace) {
  const store = useAccountPreferences(), key = `browse.${workspace}.filters` as const
  const filters = computed(() => store.values[key])
  function remember(patch: Record<string, unknown>) {
    if (!store.userId.value) return
    const next: BrowseFilters = { ...filters.value }
    for (const name of browseFilterKeys) {
      if (!Object.prototype.hasOwnProperty.call(patch, name)) continue
      const value = patch[name]
      if (typeof value === 'string' && validPreference(key, { [name]: value })) next[name] = value
    }
    if (JSON.stringify(next) !== JSON.stringify(filters.value)) store.set(key, next)
  }
  function restore(query: Record<string, unknown>, device: Record<string, unknown> = {}): Record<string, unknown> {
    if (Object.keys(query).length) return query
    const restored: Record<string, unknown> = { ...device, ...filters.value }
    if (browseFilterKeys.some(name => name in filters.value && (device[name] || '') !== filters.value[name])) {
      delete restored.page; delete restored.index_version
    }
    return restored
  }
  const formatColours = computed({ get: () => store.values['browse.format_colours'], set: value => store.set('browse.format_colours', value) })
  const showLabels = computed({ get: () => store.values['browse.original_labels'], set: value => store.set('browse.original_labels', value) })
  return { filters, remember, restore, formatColours, showLabels }
}
