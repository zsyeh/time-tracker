<script setup lang="ts">
import { uiText } from '../lib/uiText'
import { computed, onMounted, ref } from 'vue'
import { api, post, remove } from '../lib/api'
import { runtimeWorkspace } from '../lib/runtimePath'
import { useUiPreferences } from '../lib/uiPreferences'
import { learningSharePrompt } from '../lib/learningSharePrompt'

const props = defineProps<{ currentScope?: Record<string, string> }>()
type ShareKind = 'heatmap' | 'daily' | 'weekly' | 'global'
type ShareRecord = { id: number; kind: ShareKind; scope: Record<string, string>; include_notes: boolean; expires_at: string }
type Created = ShareRecord & { url: string }
const kind = ref<ShareKind>('heatmap')
const range = ref('current')
const includeNotes = ref(true)
const date = ref('')
const records = ref<ShareRecord[]>([])
const savedLinks = ref<Record<number, string>>({})
const storageKey = `learning.share.links.v1.${runtimeWorkspace}`
const created = ref<Created | null>(null)
const busy = ref(false)
const error = ref('')
const copied = ref('')
const fallbackMarkdown = ref('')
const { language } = useUiPreferences()
const labels = computed(() => language.value === 'zh-CN' ? {
  title: 'AI 分享 · 7 天', workspace: '工作区', access: '分享链接有效 7 天。获得链接的人可读取所选范围内的学习记录',
  notesAccess: '及全部当前 Note', content: '内容', range: '范围', heatmap: '热力图与逐题记录', daily: '日报',
  weekly: '周报', global: '全局历史总结', current: '当前筛选范围', all: '全局题库', selected: '数学严选题',
  core: '五科核心严选', circuit: '电路严选', signal: '信号严选', analog: '模电严选', digital: '数电严选',
  communication: '通信严选', today: '今天', yesterday: '昨天', custom: '指定日期', recent7: '最近 7 天',
  previous7: '上一个 7 天', date: '日期', includeNotes: '包含当前 Note', create: '生成 7 天链接',
  sharing: '将分享', expires: '到期时间', linkLabel: 'AI 学习数据分享链接', copied: '已复制',
  copyLink: '复制链接', view: '查看内容', copyPrompt: '复制给 ChatGPT 的提示词',
  copiedMarkdown: '已复制 Markdown', copyMarkdown: '复制 Markdown 全文', revokeNow: '立即撤销',
  safariFallback: 'Safari 无法自动复制，请长按下面文本并选择“全选→复制”。', active: '有效分享',
  browserOnly: '链接仅保存在创建它的浏览器。其他设备无法从服务器恢复明文链接，可撤销后重新生成。',
  noteIncluded: '已包含', noteExcluded: '未包含', revoke: '撤销', copyFallback: '请复制以下内容',
  markdownError: 'Markdown 读取失败',
} : {
  title: 'AI share · 7 days', workspace: 'Workspace', access: 'This link expires after 7 days. Anyone with it can read learning records in the selected scope',
  notesAccess: ' and all current Notes', content: 'Content', range: 'Scope', heatmap: 'Heatmap and question records', daily: 'Daily report',
  weekly: 'Weekly report', global: 'All-time summary', current: 'Current filters', all: 'Entire question bank', selected: 'Selected math questions',
  core: 'Five-core selected set', circuit: 'Selected circuits', signal: 'Selected signals', analog: 'Selected analog', digital: 'Selected digital',
  communication: 'Selected communications', today: 'Today', yesterday: 'Yesterday', custom: 'Specific date', recent7: 'Last 7 days',
  previous7: 'Previous 7 days', date: 'Date', includeNotes: 'Include current Notes', create: 'Create 7-day link',
  sharing: 'Sharing', expires: 'Expires', linkLabel: 'AI learning-data share link', copied: 'Copied',
  copyLink: 'Copy link', view: 'View content', copyPrompt: 'Copy prompt for ChatGPT',
  copiedMarkdown: 'Markdown copied', copyMarkdown: 'Copy full Markdown', revokeNow: 'Revoke now',
  safariFallback: 'Safari could not copy automatically. Long-press the text below, then choose Select All → Copy.', active: 'Active shares',
  browserOnly: 'Plaintext links are stored only in the browser that created them. On another device, revoke and create a new link.',
  noteIncluded: 'included', noteExcluded: 'excluded', revoke: 'Revoke', copyFallback: 'Copy this content',
  markdownError: 'Could not read Markdown',
})
const kindLabel = (value: ShareKind) => ({ heatmap: labels.value.heatmap, daily: labels.value.daily, weekly: labels.value.weekly, global: labels.value.global })[value]
const scopeDescription = computed(() => {
  if (kind.value === 'global') return labels.value.global
  if (kind.value === 'heatmap' && range.value === 'current') return JSON.stringify(props.currentScope || {})
  const descriptions: Record<string, string> = {
    all: labels.value.all, selected: labels.value.selected, core_selected: labels.value.core,
    circuit_selected: labels.value.circuit, signal_selected: labels.value.signal,
    analog_selected: labels.value.analog, digital_selected: labels.value.digital,
    communication_selected: labels.value.communication, today: labels.value.today,
    yesterday: labels.value.yesterday, custom: date.value || labels.value.custom,
    recent7: labels.value.recent7, previous7: labels.value.previous7,
  }
  return descriptions[range.value] || range.value
})

async function refresh() {
  try {
    records.value = (await api<{ shares: ShareRecord[] }>('/api/drill/learning-shares/')).shares
    const active = new Set(records.value.map((item) => item.id))
    savedLinks.value = Object.fromEntries(Object.entries(savedLinks.value)
      .filter(([id]) => active.has(Number(id)))) as Record<number, string>
    localStorage.setItem(storageKey, JSON.stringify(savedLinks.value))
  }
  catch (reason) { error.value = (reason as Error).message }
}

function scope() {
  if (kind.value === 'heatmap') {
    if (range.value === 'current') return props.currentScope || {}
    if (range.value === 'all') return {}
    return { collection: range.value }
  }
  if (kind.value === 'daily') return range.value === 'custom' ? { date: date.value } : { period: range.value }
  if (kind.value === 'weekly') return { period: range.value }
  return {}
}

async function create() {
  busy.value = true
  error.value = ''
  try {
    created.value = await post<Created>('/api/drill/learning-shares/', {
      kind: kind.value, scope: scope(), include_notes: includeNotes.value,
    })
    savedLinks.value[created.value.id] = created.value.url
    await refresh()
  } catch (reason) { error.value = (reason as Error).message }
  finally { busy.value = false }
}

async function revoke(id: number) {
  busy.value = true
  error.value = ''
  try {
    await remove(`/api/drill/learning-shares/${id}/`)
    delete savedLinks.value[id]
    if (created.value?.id === id) created.value = null
    await refresh()
  } catch (reason) { error.value = (reason as Error).message }
  finally { busy.value = false }
}

async function copy(value: string, label: string) {
  try {
    await navigator.clipboard.writeText(value)
    copied.value = label
  } catch {
    window.prompt(labels.value.copyFallback, value)
  }
}

async function copyMarkdown() {
  if (!created.value) return
  busy.value = true
  error.value = ''
  try {
    const response = await fetch(created.value.url.replace(/\/index\.md$/, '/export.md'), { credentials: 'omit' })
    if (!response.ok) throw new Error(`${labels.value.markdownError} (${response.status})`)
    const body = await response.text()
    try {
      await navigator.clipboard.writeText(body)
      copied.value = 'markdown'
      fallbackMarkdown.value = ''
    } catch {
      fallbackMarkdown.value = body
    }
  } catch (reason) { error.value = (reason as Error).message }
  finally { busy.value = false }
}

const prompt = computed(() => created.value
  ? learningSharePrompt(runtimeWorkspace, created.value.url, language.value)
  : '')
onMounted(() => {
  try { savedLinks.value = JSON.parse(localStorage.getItem(storageKey) || '{}') as Record<number, string> }
  catch { savedLinks.value = {} }
  void refresh()
})
</script>

<template>
  <details class="learning-share-panel">
    <summary>{{ labels.title }}</summary>
    <p>{{ labels.workspace }}：<a href="https://drill.ehzsy.site/insight" :aria-current="runtimeWorkspace === 'drill' ? 'page' : undefined">Drill</a> ·
      <a href="https://ei.ehzsy.site/insight" :aria-current="runtimeWorkspace === 'ei' ? 'page' : undefined">EI</a></p>
    <p>{{ labels.access }}<span v-if="includeNotes">{{ labels.notesAccess }}</span>{{ language === 'zh-CN' ? '。' : '.' }}</p>
    <div class="learning-share-controls">
      <label>{{ labels.content }}
        <select v-model="kind" @change="range = kind === 'heatmap' ? 'current' : kind === 'daily' ? 'today' : 'recent7'">
          <option value="heatmap">{{ labels.heatmap }}</option><option value="daily">{{ labels.daily }}</option>
          <option value="weekly">{{ labels.weekly }}</option><option value="global">{{ labels.global }}</option>
        </select>
      </label>
      <label v-if="kind !== 'global'">{{ labels.range }}
        <select v-model="range">
          <template v-if="kind === 'heatmap'">
            <option value="current">{{ labels.current }}</option><option value="all">{{ labels.all }}</option>
            <option v-if="runtimeWorkspace === 'drill'" value="selected">{{ labels.selected }}</option>
            <template v-else>
              <option value="core_selected">{{ labels.core }}</option>
              <option value="circuit_selected">{{ labels.circuit }}</option><option value="signal_selected">{{ labels.signal }}</option>
              <option value="analog_selected">{{ labels.analog }}</option><option value="digital_selected">{{ labels.digital }}</option>
              <option value="communication_selected">{{ labels.communication }}</option>
            </template>
          </template>
          <template v-else-if="kind === 'daily'"><option value="today">{{ labels.today }}</option><option value="yesterday">{{ labels.yesterday }}</option><option value="custom">{{ labels.custom }}</option></template>
          <template v-else><option value="recent7">{{ labels.recent7 }}</option><option value="previous7">{{ labels.previous7 }}</option></template>
        </select>
      </label>
      <label v-if="kind === 'daily' && range === 'custom'">{{ labels.date }}<input v-model="date" type="date"></label>
      <label class="note-choice"><input v-model="includeNotes" type="checkbox">{{ labels.includeNotes }}</label>
      <button type="button" :disabled="busy || (kind === 'daily' && range === 'custom' && !date)" @click="create">{{ labels.create }}</button>
    </div>
    <p class="scope">{{ labels.sharing }}：{{ scopeDescription }}</p>
    <p v-if="error" role="alert">{{ uiText(error) }}</p>
    <div v-if="created" class="created-share">
      <p>{{ labels.expires }}：{{ new Date(created.expires_at).toLocaleString(language) }}</p>
      <input :value="created.url" readonly :aria-label="labels.linkLabel" @focus="($event.target as HTMLInputElement).select()">
      <div class="share-actions">
        <button type="button" @click="copy(created.url, 'link')">{{ copied === 'link' ? labels.copied : labels.copyLink }}</button>
        <a :href="created.url" target="_blank" rel="noopener noreferrer">{{ labels.view }}</a>
        <button type="button" @click="copy(prompt, 'prompt')">{{ copied === 'prompt' ? labels.copied : labels.copyPrompt }}</button>
        <button type="button" :disabled="busy" @click="copyMarkdown">{{ copied === 'markdown' ? labels.copiedMarkdown : labels.copyMarkdown }}</button>
        <button type="button" class="share-revoke" :disabled="busy" @click="revoke(created.id)">{{ labels.revokeNow }}</button>
      </div>
      <label v-if="fallbackMarkdown">{{ labels.safariFallback }}
        <textarea :value="fallbackMarkdown" readonly rows="8" @focus="($event.target as HTMLTextAreaElement).select()" />
      </label>
    </div>
    <details v-if="records.length"><summary>{{ labels.active }} ({{ records.length }})</summary>
      <p>{{ labels.browserOnly }}</p>
      <ul><li v-for="item in records" :key="item.id">{{ kindLabel(item.kind) }} · {{ labels.expires }} {{ new Date(item.expires_at).toLocaleString(language) }} · Note {{ item.include_notes ? labels.noteIncluded : labels.noteExcluded }}
        <button v-if="savedLinks[item.id]" type="button" @click="copy(savedLinks[item.id], `record-${item.id}`)">{{ labels.copyLink }}</button>
        <a v-if="savedLinks[item.id]" :href="savedLinks[item.id]" target="_blank" rel="noopener noreferrer">{{ labels.view }}</a>
        <button type="button" class="share-revoke" :disabled="busy" @click="revoke(item.id)">{{ labels.revoke }}</button></li></ul>
    </details>
  </details>
</template>

<style scoped>
.learning-share-panel { box-sizing: border-box; width: fit-content; max-width: 100%; margin: 8px 0 12px; color: var(--text-primary); }
.learning-share-panel[open] { width: 100%; padding-block: 8px 16px; border-bottom: 1px solid var(--border-subtle); }
.learning-share-panel > summary { display: flex; align-items: center; gap: 8px; min-height: 44px; padding: 4px 8px; color: var(--text-secondary); font-size: 13px; font-weight: 550; cursor: pointer; list-style: none; }
.learning-share-panel > summary::-webkit-details-marker { display: none; }
.learning-share-panel > summary::before { content: '›'; display: inline-block; color: var(--text-secondary); font-size: 16px; }
.learning-share-panel[open] > summary::before { transform: rotate(90deg); }
.learning-share-panel details summary { min-height: 44px; cursor: pointer; font-size: 14px; font-weight: 600; }
.learning-share-panel p { color: var(--text-secondary); font-size: 13px; line-height: 1.5; }
.learning-share-panel a { color: var(--accent-ink, var(--accent)); }
.learning-share-controls, .share-actions { display: flex; flex-wrap: wrap; gap: 12px; align-items: end; }
.learning-share-controls label { display: grid; gap: 8px; min-width: 0; color: var(--text-primary); font-size: 13px; }
.learning-share-controls .note-choice { display: flex; align-items: center; min-height: 44px; }
.learning-share-panel button, .learning-share-panel select, .learning-share-panel input { min-height: 44px; color: var(--text-primary); background: var(--bg-surface); border: 1px solid var(--border-default); border-radius: 6px; font-size: 14px; }
.learning-share-panel input[type="checkbox"] { min-height: auto; accent-color: var(--accent); }
.learning-share-panel button { padding: 8px 12px; border: 0; background: var(--surface-hover, var(--bg-sidebar)); cursor: pointer; }
.learning-share-panel button:hover:not(:disabled) { background: var(--surface-selected, var(--bg-surface-active)); }
.learning-share-panel button:focus-visible { outline: 2px solid var(--accent-ink, var(--accent)); outline-offset: 2px; }
.learning-share-controls > button { color: var(--accent-on-solid, var(--text-primary)); background: var(--accent-solid, var(--accent)); font-weight: 600; }
.learning-share-controls > button:hover:not(:disabled) { background: var(--accent-solid, var(--accent)); filter: brightness(.94); }
.learning-share-panel button.share-revoke { color: var(--danger); background: transparent; }
.learning-share-panel input, .learning-share-panel select, .learning-share-panel textarea { min-width: 0; max-width: 100%; padding: 8px; }
.created-share input, .created-share textarea { box-sizing: border-box; width: 100%; }
.created-share textarea { min-height: 10rem; color: var(--text-primary); background: var(--bg-surface); border: 1px solid var(--border-default); font-size: 14px; }
.learning-share-panel ul { display: grid; gap: 8px; margin: 8px 0; padding: 0; list-style: none; }
.learning-share-panel li { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding-block: 8px; border-top: 1px solid var(--border-subtle); font-size: 13px; }
.scope { overflow-wrap: anywhere; }
</style>
