/** Test-only authenticated fixture for components using account-owned preferences. */
import { accountPreferences } from './store'
import { preferenceDefaults, type PreferenceSnapshot, type PreferenceValues } from './schema'
export async function bindTestPreferences(language: PreferenceValues['language'] = 'en', id = 'component-test-account') {
  const snapshot: PreferenceSnapshot = { schema_version: 1, revision: 0,
    values: { ...preferenceDefaults(), language }, field_revisions: {} }
  await accountPreferences.bind(id, snapshot)
  return snapshot
}
export function clearTestPreferences() { accountPreferences.reset(true); accountPreferences.dispose() }
