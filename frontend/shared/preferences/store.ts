import { computed, reactive, ref } from 'vue'
import { applyVisualPreferences, persistVisualPreferences, VISUAL_COOKIE, VISUAL_KEY } from '../appearance/resolve'
import { readPreferenceBootstrap } from './bootstrap'
import { fontScales, preferenceDefaults, validSnapshot, validPreference, type PreferenceKey, type PreferenceSnapshot, type PreferenceValues } from './schema'

type Pending = { value: unknown; base: number; serial: number }
type Reply = { status: number; body: unknown }
export type PreferencesTransport = (method: 'GET'|'PATCH', payload?: unknown, signal?: AbortSignal, expectedUserId?: string) => Promise<Reply>
const clone = <T>(value:T):T => JSON.parse(JSON.stringify(value)) as T
const same = (left:unknown,right:unknown) => JSON.stringify(left) === JSON.stringify(right)
const emptySnapshot = ():PreferenceSnapshot => ({ schema_version:1, revision:0, values:preferenceDefaults(), field_revisions:{} })
const cacheKey = (id:string) => `learning.preferences.v1.${id}`
function readCache(id:string) {
  try {
    const cached = JSON.parse(localStorage.getItem(cacheKey(id)) || 'null')
    // Additive v1 upgrade: preserve the account's offline queue, but never repair
    // a corrupt existing field or invent missing pre-existing required fields.
    if (cached?.snapshot?.values && typeof cached.snapshot.values === 'object' && !Array.isArray(cached.snapshot.values)) {
      const values = { ...cached.snapshot.values }
      for (const key of ['progress.drill', 'progress.ei'] as const) {
        if (!Object.prototype.hasOwnProperty.call(values, key)) values[key] = preferenceDefaults()[key]
      }
      return { ...cached, snapshot: { ...cached.snapshot, values } }
    }
    return cached
  } catch { return null }
}
function appearance(values:PreferenceValues) {
  const visual = { version:1 as const, appearance:values.appearance, accent:values.accent }
  applyVisualPreferences(visual)
  if (typeof document !== 'undefined') {
    document.documentElement.style.setProperty('--ui-font-scale', String(fontScales[values.font] || .95))
    document.documentElement.dataset.fontSize = values.font
    document.documentElement.lang = values.language
  }
  if (typeof window !== 'undefined') window.dispatchEvent(new CustomEvent('learning:preferences-changed'))
}
export async function preferencesTransport(method:'GET'|'PATCH', payload?:unknown, signal?:AbortSignal, expectedUserId?:string):Promise<Reply> {
  const prefix = typeof location !== 'undefined' ? location.pathname.match(/^\/(drill|ei)(?:\/|$)/)?.[0].replace(/\/$/,'') || '' : ''
  const headers:Record<string,string> = { Accept:'application/json' }
  if (expectedUserId) headers['X-Learning-User-ID'] = expectedUserId
  if (payload !== undefined) {
    headers['Content-Type'] = 'application/json'
    const cookie = typeof document === 'undefined' ? null : document.cookie.split(';').map(v=>v.trim()).find(v=>v.startsWith('csrftoken='))
    if (cookie) headers['X-CSRFToken'] = decodeURIComponent(cookie.slice(10))
  }
  const response = await fetch(`${prefix}/api/user-preferences/`, { method, headers, credentials:'same-origin', cache:'no-store', signal, ...(payload === undefined ? {} : { body:JSON.stringify(payload) }) })
  let body:unknown = null
  try { body = await response.json() } catch { /* A proxy error must leave the queue recoverable. */ }
  return { status:response.status, body }
}
export function createPreferencesStore(transport:PreferencesTransport=preferencesTransport) {
  const seed=readPreferenceBootstrap()
  const values=reactive<PreferenceValues>(preferenceDefaults())
  const userId=ref<string|null>(null), status=ref<'idle'|'loading'|'saved'|'saving'|'offline'|'error'|'conflict'>('idle')
  const message=ref(''), conflicts=ref<PreferenceKey[]>([])
  let server=emptySnapshot(), pending:Partial<Record<PreferenceKey,Pending>>={}, serial=0, epoch=0
  let timer:ReturnType<typeof setTimeout>|undefined, polling:ReturnType<typeof setInterval>|undefined
  let currentRequest:AbortController|undefined, saving=false, refreshing=false, started=false, bound=false
  let inFlight = new Set<PreferenceKey>()
  const serverRevision=ref(0)
  const pendingCount=ref(0)
  const keys=() => Object.keys(pending) as PreferenceKey[]
  function cache() {
    pendingCount.value=keys().length
    if (!userId.value) return
    try { localStorage.setItem(cacheKey(userId.value),JSON.stringify({ snapshot:server,pending })) } catch { /* Storage failure never blocks study. */ }
  }
  function render(persist=true) {
    Object.assign(values,clone(server.values))
    for (const key of keys()) Object.assign(values,{ [key]:clone(pending[key]!.value) })
    appearance(values)
    // Device cookies are only a boot/legacy adapter, never the authority. The
    // authenticated server HTML overrides them before the first application frame.
    if (userId.value) persistVisualPreferences({ version:1,appearance:values.appearance,accent:values.accent })
    if(persist)cache()
  }
  function accept(snapshot:PreferenceSnapshot) {
    server=clone(snapshot);serverRevision.value=server.revision
    for (const key of keys()) {
      if (same(pending[key]!.value,server.values[key])) delete pending[key]
    }
    conflicts.value=conflicts.value.filter(key=>!!pending[key])
    render()
  }
  function schedule() { clearTimeout(timer); if (userId.value) timer=setTimeout(()=>{ void flush() },500) }
  function set<K extends PreferenceKey>(key:K,value:PreferenceValues[K]) {
    if (!userId.value) { message.value='请先登录以保存账号预设。'; return }
    if (same(values[key],value)) return
    const previous=pending[key]
    pending[key]={ value:clone(value),base:previous?.base ?? server.field_revisions[key] ?? 0,serial:++serial }
    if (same(server.values[key],value) && !inFlight.has(key)) delete pending[key]
    conflicts.value=conflicts.value.filter(item=>!!pending[item])
    if(!saving)status.value=conflicts.value.length?'conflict':keys().length?'idle':'saved'
    message.value='';render();schedule()
  }
  async function bind(id:string|number,snapshot?:PreferenceSnapshot) {
    const next=String(id)
    if (next !== userId.value || !bound) {
      bound=true
      epoch++;clearTimeout(timer);currentRequest?.abort();saving=false;refreshing=false
      userId.value=next;pending={};conflicts.value=[];server=emptySnapshot();inFlight.clear()
      const cached=readCache(next)
      if (validSnapshot(cached?.snapshot)) {
        server=clone(cached.snapshot)
        for (const [key,item] of Object.entries(cached.pending || {})) {
          if (!(key in preferenceDefaults()) || !item || typeof item !== 'object') continue
          const value=item as Pending
          if (Number.isSafeInteger(value.base) && value.base>=0 && Number.isSafeInteger(value.serial) && validPreference(key,value.value)) {
            // Only entries originally written by this same authenticated account
            // are restored. Server validation remains mandatory on every write.
            pending[key as PreferenceKey]=clone(value);serial=Math.max(serial,value.serial)
          }
        }
      }
      if(validSnapshot(snapshot))server=clone(snapshot)
      render()
    }
    if (validSnapshot(snapshot)) {
      accept(snapshot)
      conflicts.value=keys().filter(key=>pending[key]!.base !== (server.field_revisions[key] ?? 0))
      status.value=conflicts.value.length?'conflict':keys().length?'idle':'saved'
      if (keys().length) schedule()
    } else await refresh()
    start()
  }
  function accountChanged(reply:Reply) {
    const detail=(reply.body as {detail?:unknown})?.detail
    if(reply.status!==401 && !(reply.status===403 && typeof detail==='string' && /authentication credentials|not authenticated/i.test(detail)) && !(reply.status===409 && typeof detail==='string' && detail.startsWith('Account changed.')))return false
    // Keep the old account's scoped offline queue, but remove its private labels
    // from the live UI as soon as the server rejects that account affinity.
    reset();status.value='error';message.value='登录账号已变化，请刷新页面后继续同步。';return true
  }
  async function flush() {
    clearTimeout(timer)
    if (!userId.value || saving) return
    const batch=keys().filter(key=>!conflicts.value.includes(key))
    if (!batch.length) { status.value=conflicts.value.length?'conflict':'saved';return }
    const sent=Object.fromEntries(batch.map(key=>[key,clone(pending[key]!)])) as Partial<Record<PreferenceKey,Pending>>
    const generation=epoch, expectedUserId=userId.value;currentRequest=new AbortController();const controller=currentRequest
    const timeout=setTimeout(()=>controller.abort(),8000)
    saving=true;inFlight=new Set(batch);status.value='saving';message.value=''
    try {
      const reply=await transport('PATCH',{ schema_version:1,changes:Object.fromEntries(batch.map(key=>[key,sent[key]!.value])),base_revisions:Object.fromEntries(batch.map(key=>[key,sent[key]!.base])) },controller.signal,expectedUserId)
      if (generation!==epoch) return
      if(accountChanged(reply))return
      if (reply.status===200 && validSnapshot(reply.body)) {
        const snapshot=reply.body
        for (const key of batch) {
          if (pending[key]?.serial===sent[key]!.serial) delete pending[key]
          else if (pending[key]) pending[key]!.base=snapshot.field_revisions[key] ?? 0
        }
        // A concurrent GET can already have observed this commit plus a newer
        // device update. A late acknowledgement must not roll that snapshot back.
        if(snapshot.revision>=server.revision)accept(snapshot)
        else render()
        conflicts.value=keys().filter(key=>pending[key]!.base!==(server.field_revisions[key]??0))
        status.value=conflicts.value.length?'conflict':keys().length?'idle':'saved'
        if (keys().some(key=>!conflicts.value.includes(key))) schedule()
      } else if (reply.status===409 && validSnapshot((reply.body as {current?:unknown})?.current)) {
        const error=reply.body as {current:PreferenceSnapshot;conflicts:PreferenceKey[]}
        if(error.current.revision>=server.revision)accept(error.current)
        conflicts.value=keys().filter(key=>pending[key]!.base!==(server.field_revisions[key]??0))
        status.value='conflict';message.value='另一设备已修改相同预设。请选择保留本机更改或使用服务器版本。';cache()
        if (keys().some(key=>!conflicts.value.includes(key))) schedule()
      } else {
        status.value='error';message.value=reply.status===401||reply.status===403?'登录或权限已变化，预设尚未同步。':'预设保存失败，更改保留在本机。请重试。';cache()
      }
    } catch {
      if (generation!==epoch) return
      status.value='offline';message.value='暂时无法同步，预设已保留。恢复连接后会重试，不影响做题。';cache()
    } finally { clearTimeout(timeout);if(generation===epoch) {saving=false;inFlight.clear()} }
  }
  async function refresh() {
    if (!userId.value || refreshing || saving) return
    const generation=epoch, expectedUserId=userId.value;refreshing=true
    const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),5000)
    try {
      const reply=await transport('GET',undefined,controller.signal,expectedUserId)
      if (generation!==epoch) return
      if(accountChanged(reply))return
      if (reply.status===200 && validSnapshot(reply.body)) {
        if(reply.body.revision < server.revision)return
        message.value=''
        accept(reply.body)
        conflicts.value=keys().filter(key=>pending[key]!.base!==(server.field_revisions[key]??0))
        status.value=conflicts.value.length?'conflict':keys().length?'idle':'saved'
        if (keys().length) schedule()
      } else { status.value='error';message.value='尚未读取服务器预设，当前缓存仍可使用。' }
    } catch { if(generation===epoch) {status.value='offline';message.value='离线使用上次预设；恢复连接后将同步。'} }
    finally {clearTimeout(timeout);if(generation===epoch) refreshing=false}
  }
  function useServer(key?:PreferenceKey) {
    for (const item of key?[key]:conflicts.value) delete pending[item]
    conflicts.value=conflicts.value.filter(item=>!!pending[item]);render();status.value=keys().length?'idle':'saved'
    if(keys().length)schedule()
  }
  function keepMine(key?:PreferenceKey) {
    for (const item of key?[key]:conflicts.value) if(pending[item])pending[item]!.base=server.field_revisions[item]??0
    conflicts.value=conflicts.value.filter(item=>pending[item] && pending[item]!.base!==(server.field_revisions[item]??0));render();schedule()
  }
  function reset(logout=false) {
    const old=userId.value;epoch++;clearTimeout(timer);currentRequest?.abort();saving=false;refreshing=false;pending={};inFlight.clear();bound=false;userId.value=null;conflicts.value=[];server=emptySnapshot();serverRevision.value=0;status.value='idle';message.value=''
    if(logout&&old)try{localStorage.removeItem(cacheKey(old))}catch{}
    try{localStorage.removeItem(VISUAL_KEY)}catch{}
    if(typeof document!=='undefined')for(const domain of ['',...(location.hostname.endsWith('.ehzsy.site')?['; Domain=.ehzsy.site']:[])])document.cookie=`${VISUAL_COOKIE}=; Path=/; Max-Age=0${domain}`
    render()
  }
  const active = () => { if(typeof document==='undefined'||document.visibilityState!=='hidden')void refresh() }
  const online = () => { void refresh().then(()=>flush()) }
  function start() {
    if(started||typeof window==='undefined')return
    started=true;window.addEventListener('focus',active);window.addEventListener('pageshow',active);window.addEventListener('online',online)
    document.addEventListener('visibilitychange',active)
    polling=setInterval(active,30000)
  }
  function dispose(){clearTimeout(timer);clearInterval(polling);currentRequest?.abort();if(typeof window!=='undefined'){window.removeEventListener('focus',active);window.removeEventListener('pageshow',active);window.removeEventListener('online',online);document.removeEventListener('visibilitychange',active)}started=false}
  if(seed?.user_id && seed.snapshot) {userId.value=seed.user_id;server=clone(seed.snapshot);serverRevision.value=server.revision;render(false)}
  return { values,userId,status,message,conflicts,pendingCount,revision:computed(()=>serverRevision.value),set,bind,flush,refresh,useServer,keepMine,reset,dispose }
}
export const accountPreferences=createPreferencesStore()
export function useAccountPreferences(){return accountPreferences}
