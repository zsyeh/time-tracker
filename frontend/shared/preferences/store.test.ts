// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createPreferencesStore, type PreferencesTransport } from './store'
import { preferenceDefaults, type PreferenceKey, type PreferenceSnapshot, type PreferenceValues } from './schema'
import { VISUAL_KEY, VISUAL_COOKIE } from '../appearance/resolve'
import { api } from '../../drill/src/lib/api'

type Reply = Awaited<ReturnType<PreferencesTransport>>
type Patch = { schema_version: number; changes: Partial<PreferenceValues>; base_revisions: Partial<Record<PreferenceKey, number>> }
const copy = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T
function snapshot(revision = 0, changes: Partial<PreferenceValues> = {}, revisions: Partial<Record<PreferenceKey, number>> = {}): PreferenceSnapshot {
  return { schema_version: 1, revision, values: { ...preferenceDefaults(), ...copy(changes) }, field_revisions: { ...revisions } }
}
function deferred<T>() {
  let resolve!: (value: T) => void, reject!: (error: unknown) => void
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
const stores: ReturnType<typeof createPreferencesStore>[] = []
function factory(transport: PreferencesTransport) { const store = createPreferencesStore(transport); stores.push(store); return store }
async function settle() { for (let n = 0; n < 8; n++) await Promise.resolve() }
function seed(user = 'account-a', data = snapshot()) {
  const node = document.createElement('script'); node.id = 'learning-user-preferences'; node.type = 'application/json'
  node.textContent = JSON.stringify({ user_id: user, snapshot: data }); document.head.append(node)
}
/** Independent contract server: atomic field-CAS, no complete-object overwrite. */
function server(initial = snapshot()) {
  let current = copy(initial)
  const calls: Array<{ method: string; patch?: Patch }> = []
  const transport = vi.fn<PreferencesTransport>(async (method, payload) => {
    if (method === 'GET') { calls.push({ method }); return { status: 200, body: copy(current) } }
    const patch = copy(payload as Patch); calls.push({ method, patch })
    const keys = Object.keys(patch.changes) as PreferenceKey[]
    const conflicts = keys.filter(key => (patch.base_revisions[key] ?? -1) !== (current.field_revisions[key] ?? 0))
    if (conflicts.length) return { status: 409, body: { current: copy(current), conflicts } }
    current.revision += 1
    for (const key of keys) { Object.assign(current.values, { [key]: patch.changes[key] }); current.field_revisions[key] = current.revision }
    return { status: 200, body: copy(current) }
  })
  return { transport, calls, read: () => copy(current) }
}
beforeEach(() => {
  vi.useFakeTimers(); localStorage.clear(); document.getElementById('learning-user-preferences')?.remove()
  document.cookie = `${VISUAL_COOKIE}=; Path=/; Max-Age=0`
  vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })))
})
afterEach(() => {
  for (const store of stores.splice(0)) store.dispose()
  document.getElementById('learning-user-preferences')?.remove(); vi.unstubAllGlobals(); vi.restoreAllMocks(); vi.useRealTimers()
})

it('preserves an offline queued change across SSR bootstrap and same-account restart', async () => {
  const data = snapshot(7, { accent: 'pink' }, { accent: 7 })
  seed('account-a', data)
  localStorage.setItem('learning.preferences.v1.account-a', JSON.stringify({ snapshot: data,
    pending: { font: { value: 'large', base: 0, serial: 14 } } }))
  const remote = server(data), store = factory(remote.transport)
  expect(JSON.parse(localStorage.getItem('learning.preferences.v1.account-a')!).pending.font.value).toBe('large')
  await store.bind('account-a', data)
  expect(store.values.accent).toBe('pink'); expect(store.values.font).toBe('large'); expect(store.pendingCount.value).toBe(1)
  expect(remote.transport).not.toHaveBeenCalled()
  await vi.advanceTimersByTimeAsync(500)
  expect(remote.calls[0]?.patch?.changes).toEqual({ font: 'large' })
  expect(remote.calls[0]?.patch?.base_revisions).toEqual({ font: 0 })
  expect(store.status.value).toBe('saved'); expect(remote.read().values.font).toBe('large')
})

it('keeps the final System intent when Dark is already in flight', async () => {
  const first = deferred<Reply>(), transport = vi.fn<PreferencesTransport>()
    .mockImplementationOnce(() => first.promise)
    .mockResolvedValueOnce({ status: 200, body: snapshot(2, { appearance: 'system' }, { appearance: 2 }) })
  const store = factory(transport); await store.bind('account-a', snapshot())
  store.set('appearance', 'dark'); const saving = store.flush()
  expect(store.values.appearance).toBe('dark')
  store.set('appearance', 'system'); expect(store.values.appearance).toBe('system')
  first.resolve({ status: 200, body: snapshot(1, { appearance: 'dark' }, { appearance: 1 }) }); await saving
  expect(store.values.appearance).toBe('system'); expect(store.pendingCount.value).toBe(1)
  await vi.advanceTimersByTimeAsync(500)
  expect(transport.mock.calls[1]?.[1]).toMatchObject({ changes: { appearance: 'system' }, base_revisions: { appearance: 1 } })
  expect(store.values.appearance).toBe('system'); expect(store.pendingCount.value).toBe(0); expect(store.status.value).toBe('saved')
})

it('does not let an older GET overwrite a successfully saved PATCH', async () => {
  const get = deferred<Reply>(), patch = deferred<Reply>()
  const transport = vi.fn<PreferencesTransport>((method) => method === 'GET' ? get.promise : patch.promise)
  const store = factory(transport); await store.bind('account-a', snapshot())
  const reading = store.refresh(); store.set('accent', 'pink'); const writing = store.flush()
  patch.resolve({ status: 200, body: snapshot(1, { accent: 'pink' }, { accent: 1 }) }); await writing
  get.resolve({ status: 200, body: snapshot() }); await reading
  expect(store.values.accent).toBe('pink'); expect(store.revision.value).toBe(1); expect(store.pendingCount.value).toBe(0)
})

it('does not roll back a newer accepted GET when an older PATCH response arrives later', async () => {
  const get = deferred<Reply>(), patch = deferred<Reply>()
  const transport = vi.fn<PreferencesTransport>((method) => method === 'GET' ? get.promise : patch.promise)
  const store = factory(transport); await store.bind('account-a', snapshot())
  const reading = store.refresh(); store.set('accent', 'pink'); const writing = store.flush()
  get.resolve({ status: 200, body: snapshot(2, { accent: 'pink', font: 'large' }, { accent: 1, font: 2 }) }); await reading
  expect(store.values.font).toBe('large'); expect(store.revision.value).toBe(2)
  patch.resolve({ status: 200, body: snapshot(1, { accent: 'pink' }, { accent: 1 }) }); await writing
  expect(store.values.font).toBe('large'); expect(store.values.accent).toBe('pink'); expect(store.revision.value).toBe(2)
})

it('merges different fields from two devices without sending a stale full configuration', async () => {
  const remote = server(), a = factory(remote.transport), b = factory(remote.transport)
  await a.bind('account-a', snapshot()); await b.bind('account-a', snapshot())
  a.set('accent', 'pink'); await a.flush()
  b.set('font', 'large'); await b.flush()
  expect(remote.calls.filter(call => call.method === 'PATCH').map(call => call.patch?.changes)).toEqual([{ accent: 'pink' }, { font: 'large' }])
  expect(b.values.accent).toBe('pink'); expect(b.values.font).toBe('large')
  await a.refresh(); expect(a.values.font).toBe('large'); expect(a.values.accent).toBe('pink')
  expect(a.status.value).toBe('saved'); expect(b.status.value).toBe('saved')
})

it.each(['useServer', 'keepMine'] as const)('requires explicit %s after a two-device same-field 409', async (resolution) => {
  const remote = server(), a = factory(remote.transport), b = factory(remote.transport)
  await a.bind('account-a', snapshot()); await b.bind('account-a', snapshot())
  a.set('appearance', 'dark'); await a.flush()
  b.set('appearance', 'light'); await b.flush()
  expect(b.status.value).toBe('conflict'); expect(b.conflicts.value).toEqual(['appearance']); expect(b.values.appearance).toBe('light')
  const before = remote.calls.length; await vi.advanceTimersByTimeAsync(600)
  expect(remote.calls).toHaveLength(before); expect(remote.read().values.appearance).toBe('dark')
  b[resolution]('appearance')
  if (resolution === 'keepMine') {
    await vi.advanceTimersByTimeAsync(500)
    expect(remote.calls.at(-1)?.patch?.base_revisions).toEqual({ appearance: 1 })
    expect(remote.read().values.appearance).toBe('light')
  } else { expect(b.values.appearance).toBe('dark'); expect(remote.calls).toHaveLength(before) }
  expect(b.pendingCount.value).toBe(0); expect(b.conflicts.value).toEqual([]); expect(b.status.value).toBe('saved')
})

it('uses optimistic cached settings while offline and retries the queued fields on reconnect', async () => {
  const remote = server(); let offline = true
  const transport = vi.fn<PreferencesTransport>((method, payload, signal) => offline ? Promise.reject(new Error('offline')) : remote.transport(method, payload, signal))
  const store = factory(transport); await store.bind('account-a', snapshot())
  store.set('font', 'large'); await store.flush()
  expect(store.values.font).toBe('large'); expect(store.status.value).toBe('offline')
  const cached = JSON.parse(localStorage.getItem('learning.preferences.v1.account-a')!)
  expect(cached.pending.font.value).toBe('large')
  offline = false; window.dispatchEvent(new Event('online')); await settle()
  expect(remote.read().values.font).toBe('large'); expect(store.status.value).toBe('saved'); expect(store.pendingCount.value).toBe(0)
  expect(remote.calls.filter(call => call.method === 'PATCH')).toHaveLength(1)
})

it.each(['GET', 'PATCH'] as const)('ignores a late %s from the previous account even when the network ignores AbortSignal', async (method) => {
  const late = deferred<Reply>(), transport = vi.fn<PreferencesTransport>(() => late.promise)
  const store = factory(transport); await store.bind('account-a', snapshot())
  let old: Promise<void>
  if (method === 'PATCH') { store.set('accent', 'pink'); old = store.flush() } else old = store.refresh()
  await store.bind('account-b', snapshot(3, { accent: 'green', font: 'large' }, { accent: 3, font: 2 }))
  late.resolve({ status: 200, body: snapshot(1, { accent: 'pink' }, { accent: 1 }) }); await old
  expect(store.userId.value).toBe('account-b'); expect(store.values.accent).toBe('green'); expect(store.values.font).toBe('large'); expect(store.revision.value).toBe(3)
  expect(localStorage.getItem('learning.preferences.v1.account-b')).not.toContain('pink')
})

it('removes the active account cache and visual adapter on logout and rejects unauthenticated writes', async () => {
  const remote = server(), store = factory(remote.transport); await store.bind('account-a', snapshot())
  store.set('accent', 'pink'); expect(localStorage.getItem(VISUAL_KEY)).toContain('pink')
  store.reset(true)
  expect(store.userId.value).toBeNull(); expect(store.values.accent).toBe('blue'); expect(store.pendingCount.value).toBe(0)
  expect(localStorage.getItem('learning.preferences.v1.account-a')).toBeNull(); expect(localStorage.getItem(VISUAL_KEY)).toBeNull()
  expect(document.cookie).not.toContain(VISUAL_COOKIE)
  store.set('appearance', 'dark'); await store.flush(); await vi.advanceTimersByTimeAsync(600)
  expect(remote.transport).not.toHaveBeenCalled(); expect(store.values.appearance).toBe('system'); expect(store.message.value).not.toBe('')
})

it('does not wait for a stalled preference save before an independent core question request completes', async () => {
  const late = deferred<Reply>(), store = factory(() => late.promise)
  await store.bind('account-a', snapshot()); store.set('accent', 'pink'); const saving = store.flush()
  const coreFetch = vi.fn().mockResolvedValue({ status: 200, ok: true, json: async () => ({ uuid: 'core-question' }) })
  vi.stubGlobal('fetch', coreFetch)
  expect(await api('/api/drill/questions/core-question/')).toEqual({ uuid: 'core-question' })
  expect(store.status.value).toBe('saving')
  late.resolve({ status: 200, body: snapshot(1, { accent: 'pink' }, { accent: 1 }) }); await saving
  expect(store.status.value).toBe('saved')
})

it('keeps a newer local intent conflicted when an old PATCH ack arrives behind a newer same-field remote edit', async () => {
  const get = deferred<Reply>(), firstPatch = deferred<Reply>(); let writes = 0
  const transport = vi.fn<PreferencesTransport>((method) => {
    if (method === 'GET') return get.promise
    return ++writes === 1 ? firstPatch.promise : Promise.resolve({ status: 200,
      body: snapshot(3, { accent: 'purple' }, { accent: 3 }) })
  })
  const store = factory(transport); await store.bind('account-a', snapshot())
  const reading = store.refresh()
  store.set('accent', 'pink'); const writing = store.flush()
  store.set('accent', 'purple')
  get.resolve({ status: 200, body: snapshot(2, { accent: 'green' }, { accent: 2 }) }); await reading
  firstPatch.resolve({ status: 200, body: snapshot(1, { accent: 'pink' }, { accent: 1 }) }); await writing
  expect(store.values.accent).toBe('purple'); expect(store.revision.value).toBe(2)
  expect(store.status.value).toBe('conflict'); expect(store.conflicts.value).toEqual(['accent'])
  await vi.advanceTimersByTimeAsync(600); expect(writes).toBe(1)
  store.keepMine('accent'); await vi.advanceTimersByTimeAsync(500)
  expect(transport.mock.calls.at(-1)?.[1]).toMatchObject({ changes: { accent: 'purple' }, base_revisions: { accent: 2 } })
  expect(store.status.value).toBe('saved'); expect(store.values.accent).toBe('purple')
})

it('coalesces repeated touch-setting changes into one bounded write containing final field values', async () => {
  const remote = server(), store = factory(remote.transport); await store.bind('account-a', snapshot())
  for (let i = 0; i < 12; i++) {
    store.set('font', i % 2 ? 'large' : 'compact')
    await vi.advanceTimersByTimeAsync(20)
  }
  store.set('accent', 'pink'); store.set('appearance', 'dark')
  expect(remote.transport).not.toHaveBeenCalled()
  await vi.advanceTimersByTimeAsync(499); expect(remote.transport).not.toHaveBeenCalled()
  await vi.advanceTimersByTimeAsync(1)
  expect(remote.calls).toHaveLength(1)
  expect(remote.calls[0]?.patch?.changes).toEqual({ font: 'large', accent: 'pink', appearance: 'dark' })
  expect(store.status.value).toBe('saved')
})

it('pins real preference HTTP reads and writes to the bound account against cross-tab cookie identity changes', async () => {
  const network = vi.fn(async (_url: unknown, options: RequestInit) => ({
    status: 200,
    json: async () => options.method === 'PATCH'
      ? snapshot(1, { accent: 'pink' }, { accent: 1 }) : snapshot(),
  }))
  vi.stubGlobal('fetch', network)
  const store = createPreferencesStore(); stores.push(store)
  await store.bind('41', snapshot()); await store.refresh()
  store.set('accent', 'pink'); await store.flush()
  expect(network).toHaveBeenCalledTimes(2)
  for (const [, options] of network.mock.calls) {
    // The API's existing account-affinity middleware rejects a now-B cookie
    // when this A tab supplies its expected identity. Cookie auth alone cannot.
    expect(new Headers(options.headers).get('X-Learning-User-ID')).toBe('41')
    expect(options.credentials).toBe('same-origin')
  }
})

it('does not regress a newer GET snapshot when a delayed same-field 409 carries an older current snapshot', async () => {
  const get = deferred<Reply>(), patch = deferred<Reply>()
  const store = factory(method => method === 'GET' ? get.promise : patch.promise)
  await store.bind('account-a', snapshot()); const reading = store.refresh()
  store.set('accent', 'pink'); const writing = store.flush()
  get.resolve({ status: 200, body: snapshot(2, { accent: 'green', font: 'large' }, { accent: 1, font: 2 }) }); await reading
  patch.resolve({ status: 409, body: { current: snapshot(1, { accent: 'green' }, { accent: 1 }), conflicts: ['accent'] } }); await writing
  expect(store.revision.value).toBe(2); expect(store.values.font).toBe('large')
  expect(store.values.accent).toBe('pink'); expect(store.conflicts.value).toEqual(['accent']); expect(store.status.value).toBe('conflict')
})

it.each([401, 403, 409])('clears visible account preferences on auth/identity rejection %s while retaining the old private retry queue', async (status) => {
  const privatePreset = { id: 'account-a-private', name: 'Account A private preset', query: { q: '导数' } }
  const transport = vi.fn<PreferencesTransport>().mockResolvedValue({ status,
    body: { detail: status === 409 ? 'Account changed. Reload before using saved learning state.' : 'Authentication credentials were not provided.' } })
  const store = factory(transport)
  await store.bind('account-a', snapshot(1, { 'filters.drill': [privatePreset] }, { 'filters.drill': 1 }))
  store.set('font', 'large'); await store.flush()
  expect(store.userId.value).toBeNull(); expect(store.values['filters.drill']).toEqual([])
  expect(store.values.font).toBe('small'); expect(store.conflicts.value).toEqual([]); expect(store.status.value).toBe('error')
  const retained = JSON.parse(localStorage.getItem('learning.preferences.v1.account-a')!)
  expect(retained.pending.font.value).toBe('large')
  expect(retained.snapshot.values['filters.drill']).toEqual([privatePreset])
  expect(localStorage.getItem(VISUAL_KEY)).toBeNull()
  expect(store.message.value).not.toBe('')
})

it('does not discard the account or optimistic retry queue for an ordinary CSRF/permission 403', async () => {
  const store = factory(async () => ({ status: 403, body: { detail: 'CSRF Failed: token missing.' } }))
  await store.bind('account-a', snapshot()); store.set('font', 'large'); await store.flush()
  expect(store.userId.value).toBe('account-a'); expect(store.values.font).toBe('large'); expect(store.status.value).toBe('error')
  expect(JSON.parse(localStorage.getItem('learning.preferences.v1.account-a')!).pending.font.value).toBe('large')
})

it('upgrades a 14-field account cache without losing an offline pending edit', async () => {
  const old = copy(snapshot()) as any
  delete old.values['progress.drill']; delete old.values['progress.ei']; delete old.values['practice.image_copy_scale']
  delete old.values['practice.drill.study_timer_mode']; delete old.values['practice.ei.study_timer_mode']
  for (const key of ['browse.drill.filters','browse.ei.filters','browse.format_colours','browse.original_labels']) delete old.values[key]
  localStorage.setItem('learning.preferences.v1.account-a', JSON.stringify({ snapshot: old,
    pending: { font: { value: 'large', base: 0, serial: 42 } } }))
  const remote = server(), store = factory(remote.transport)
  await store.bind('account-a', snapshot())
  expect(store.values.font).toBe('large'); expect(store.pendingCount.value).toBe(1)
  expect(store.values['progress.drill']).toEqual({ target: 24, deadline: '2026-11-21' })
  expect(store.values['practice.drill.study_timer_mode']).toBe('remind')
  expect(store.values['practice.ei.study_timer_mode']).toBe('remind')
  await store.flush()
  expect(remote.calls[0]?.patch?.changes).toEqual({ font: 'large' })
  expect(store.pendingCount.value).toBe(0)
})

it.each(['invalid-goal','missing-old-field'])('does not accept a corrupt cache during additive upgrade: %s', async kind => {
  const old = copy(snapshot()) as any
  delete old.values['progress.ei']
  if(kind==='invalid-goal') old.values['progress.drill']={target:0, deadline:'bad'}
  else delete old.values.accent
  localStorage.setItem('learning.preferences.v1.account-a', JSON.stringify({ snapshot: old,
    pending: { font: { value: 'large', base: 0, serial: 42 } } }))
  const store = factory(server().transport); await store.bind('account-a', snapshot())
  expect(store.values.font).toBe('small'); expect(store.pendingCount.value).toBe(0)
})

it('adds a missing copy scale to a previous 16-field cache and keeps its queued edit', async()=>{
 const old=copy(snapshot()) as any;delete old.values['practice.image_copy_scale']
 localStorage.setItem('learning.preferences.v1.account-a',JSON.stringify({snapshot:old,pending:{font:{value:'large',base:0,serial:8}}}))
 const remote=server(),store=factory(remote.transport);await store.bind('account-a',snapshot())
 expect(store.values['practice.image_copy_scale']).toBe(1);expect(store.values.font).toBe('large')
 await store.flush();expect(remote.read().values.font).toBe('large')
})
