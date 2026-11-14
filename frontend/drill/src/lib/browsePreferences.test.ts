// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { accountPreferences as store } from '../../../shared/preferences/store'
import { preferenceDefaults, validPreference } from '../../../shared/preferences/schema'
import { useBrowsePreferences } from './browsePreferences'
async function setup() { await store.bind('browse-owner', { schema_version: 1, revision: 0, values: preferenceDefaults(), field_revisions: {} }) }
afterEach(() => { store.reset(true); store.dispose(); localStorage.clear(); vi.restoreAllMocks() })
it('shares small-question choices across views, while separating Drill and EI', async () => {
  await setup(); const a = useBrowsePreferences('drill'), b = useBrowsePreferences('drill'), ei = useBrowsePreferences('ei')
  a.remember({ type_group: 'small', favorite: '1' })
  expect(b.restore({})).toEqual({ type_group: 'small', favorite: '1' })
  expect(ei.restore({})).toEqual({})
  expect(store.pendingCount.value).toBe(1)
})
it('preserves explicit URLs, and clears an obsolete device page on changed account filters', async () => {
  await setup(); const prefs = useBrowsePreferences(); prefs.remember({ type_group: 'small' })
  expect(prefs.restore({ q: 'Fourier', page: '3' })).toEqual({ q: 'Fourier', page: '3' })
  expect(prefs.restore({ type_group: '' })).toEqual({ type_group: '' })
  expect(prefs.restore({}, { type_group: 'large', page: '20', index_version: 'old', document: '3' })).toEqual({ type_group: 'small', document: '3' })
})
it('remembers unchecked choices and does not restore a stale local selection', async () => {
  await setup(); const prefs = useBrowsePreferences(); prefs.remember({ type_group: 'small', favorite: '1' }); prefs.remember({ type_group: '', favorite: '' })
  expect(prefs.restore({}, { type_group: 'small', favorite: '1' })).toEqual({ type_group: '', favorite: '' })
  prefs.showLabels.value = false; prefs.formatColours.value = false
  expect(useBrowsePreferences('ei').showLabels.value).toBe(false)
  expect(useBrowsePreferences('ei').formatColours.value).toBe(false)
})
it('does not sync keywords, pagination, book context or invalid values', async () => {
  await setup(); const prefs = useBrowsePreferences(); prefs.remember({ q: 'private query', page: '5', document: '8', type_group: 'bad', favorite: true })
  expect(prefs.filters.value).toEqual({}); expect(store.pendingCount.value).toBe(0)
  expect(validPreference('browse.drill.filters', { page: '5' })).toBe(false)
  expect(validPreference('browse.ei.filters', { type_group: 'small', favorite: '' })).toBe(true)
  expect(validPreference('browse.format_colours', 'false')).toBe(false)
})
it('does not write for repeated unchanged selections or after logout', async () => {
  await setup(); const prefs = useBrowsePreferences(); prefs.remember({ type_group: 'small' })
  const set = vi.spyOn(store, 'set'); prefs.remember({ type_group: 'small' }); expect(set).not.toHaveBeenCalled()
  store.reset(true); prefs.remember({ type_group: 'large' }); expect(set).not.toHaveBeenCalled(); expect(prefs.filters.value).toEqual({})
})
