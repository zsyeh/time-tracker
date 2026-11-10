// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { ForegroundTimer, type TimingReply } from '../../shared/foregroundTimer'
let now = 0
let offline = false
let conflict = false
let server: TimingReply
let calls: string[]
function request<T>(_url: string, options?: RequestInit): Promise<T> {
  const data = JSON.parse(String(options?.body))
  calls.push(data.action)
  if (conflict) return Promise.reject(Object.assign(new Error('lease'), { status: 409 }))
  if (offline) return Promise.reject(new Error('offline'))
  if (data.action === 'claim') server = { ...server, timing_key: data.timing_key, owner: data.owner, sequence: Math.max(server.sequence, data.sequence), local_base_valid: true }
  else if (data.sequence > server.sequence) server = { ...server, sequence: data.sequence, elapsed_ms: Math.max(server.elapsed_ms,data.elapsed_ms), countdown_ms: data.countdown_ms }
  return Promise.resolve({ ...server } as T)
}
const timer = (user = '1', workspace = 'drill') => new ForegroundTimer(user, workspace, 'q1', request)
async function advance(t: ForegroundTimer, ms: number) {
  for (let n=0;n<ms;n+=500) { now+=500;t.tick(); await Promise.resolve();await Promise.resolve() }
}
beforeEach(() => {
  localStorage.clear();sessionStorage.clear();now=0;offline=false;conflict=false;calls=[]
  vi.spyOn(performance,'now').mockImplementation(()=>now)
  vi.spyOn(document,'visibilityState','get').mockReturnValue('visible')
  server={ protocol:2,timing_key:'',elapsed_ms:0,countdown_ms:5000,sequence:0,owner:'',finalized:false }
})
afterEach(()=>vi.restoreAllMocks())
it('retains 60 seconds through five rapid refreshes with the same round and no second warmup', async () => {
  let t=timer();await t.activate();await advance(t,65000);await t.pause()
  expect(Math.round(t.state.elapsedMs)).toBe(60000)
  const key=t.state.key
  for(let i=0;i<5;i++) { t=timer();await t.activate();expect(t.state.key).toBe(key);expect(t.state.elapsedMs).toBe(60000);expect(t.state.countdownMs).toBe(0);await t.pause() }
  await advance(t,1000);expect(t.state.elapsedMs).toBe(60000)
  await t.activate();await advance(t,1000);expect(t.state.elapsedMs).toBe(61000)
})
it('does not count hidden, lock-screen or unobservable freeze intervals', async () => {
  const t=timer();await t.activate();await advance(t,15000);await t.pause()
  await advance(t,3600000);expect(t.state.elapsedMs).toBe(10000)
  await t.activate();await advance(t,1000);expect(t.state.elapsedMs).toBe(11000)
  now+=3600000;t.tick();expect(t.state.elapsedMs).toBe(11000)
})
it('retains offline snapshots, then syncs an absolute total rather than adding it twice', async () => {
  const t=timer();await t.activate();await advance(t,15000);offline=true
  await advance(t,45000);await t.sync('checkpoint')
  expect(t.status).toBe('offline');const elapsed=t.state.elapsedMs
  offline=false;await t.activate();await t.sync('checkpoint');await t.sync('checkpoint')
  expect(server.elapsed_ms).toBe(elapsed)
  expect(t.state.elapsedMs).toBe(elapsed)
  expect(localStorage.getItem(t.storageKey)).toContain(t.state.key)
})
it('scopes data to account and workspace and resumes a different unsubmitted question locally', async () => {
  const a=timer();await a.activate();await advance(a,15000);await a.pause()
  expect(timer('2').state.elapsedMs).toBe(0)
  expect(timer('1','ei').state.elapsedMs).toBe(0)
  expect(timer().state.elapsedMs).toBe(10000)
})
it('preserves submission UUID through reload and keeps finalized rounds stopped', async () => {
  const a=timer();await a.activate();const key=a.submissionKey();a.snapshot()
  const restored=timer();expect(restored.submissionKey()).toBe(key)
  a.finish();await advance(a,30000);expect(a.state.elapsedMs).toBe(0)
  expect(timer().state.key).not.toBe(a.state.key)
})
it('stops on lease conflict without discarding its local checkpoint', async () => {
  const a=timer();await a.activate();await advance(a,15000);conflict=true
  await a.sync('checkpoint');const elapsed=a.state.elapsedMs;await advance(a,10000)
  expect(a.status).toBe('conflict');expect(a.state.elapsedMs).toBe(elapsed)
})
it('uses bounded checkpoints instead of sending each UI tick', async () => {
  const a=timer();await a.activate();await advance(a,60000);await a.pause()
  expect(calls.filter(c=>c==='checkpoint').length).toBeLessThanOrEqual(4)
  expect(calls.filter(c=>c==='pause')).toHaveLength(1)
  await a.pause();expect(calls.filter(c=>c==='pause')).toHaveLength(1)
})

it('sends the previous pause before the next question claim',async()=>{
  const first=timer();await first.activate();calls=[]
  void first.dispose()
  const next=new ForegroundTimer('1','drill','q2',request)
  await next.activate()
  expect(calls.slice(0,2)).toEqual(['pause','claim'])
  await next.pause()
})
