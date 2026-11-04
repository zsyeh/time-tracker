<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api, post, remove } from '../lib/api'
import { runtimeWorkspace } from '../lib/runtimePath'

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
const scopeDescription = computed(() => kind.value === 'heatmap'
  ? (range.value === 'current' ? JSON.stringify(props.currentScope || {}) : range.value)
  : kind.value === 'daily' || kind.value === 'weekly' ? range.value : '全局')

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
    window.prompt('请复制以下内容', value)
  }
}

async function copyMarkdown() {
  if (!created.value) return
  busy.value = true
  error.value = ''
  try {
    const response = await fetch(created.value.url.replace(/\/index\.md$/, '/export.md'), { credentials: 'omit' })
    if (!response.ok) throw new Error(`Markdown 读取失败（${response.status}）`)
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
  ? `请读取这个 ${runtimeWorkspace.toUpperCase()} 学习数据链接：${created.value.url}。沿着目录查看热力图、错误分类和重点题目，根据真实数据分析我的薄弱点，并推荐明天需要练习的 15 道题。不要编造题目数量或掌握情况。`
  : '')
onMounted(() => {
  try { savedLinks.value = JSON.parse(localStorage.getItem(storageKey) || '{}') as Record<number, string> }
  catch { savedLinks.value = {} }
  void refresh()
})
</script>

<template>
  <details class="learning-share-panel">
    <summary>分享给 AI · 7 天只读链接</summary>
    <p>工作区：<a href="https://drill.ehzsy.site/insight" :aria-current="runtimeWorkspace === 'drill' ? 'page' : undefined">Drill</a> ·
      <a href="https://ei.ehzsy.site/insight" :aria-current="runtimeWorkspace === 'ei' ? 'page' : undefined">EI</a></p>
    <p>分享链接有效 7 天。获得链接的人可读取所选范围内的学习记录<span v-if="includeNotes">及全部当前 Note</span>。</p>
    <div class="learning-share-controls">
      <label>内容
        <select v-model="kind" @change="range = kind === 'heatmap' ? 'current' : kind === 'daily' ? 'today' : 'recent7'">
          <option value="heatmap">热力图与逐题记录</option><option value="daily">日报</option>
          <option value="weekly">周报</option><option value="global">全局历史总结</option>
        </select>
      </label>
      <label v-if="kind !== 'global'">范围
        <select v-model="range">
          <template v-if="kind === 'heatmap'">
            <option value="current">当前筛选范围</option><option value="all">全局题库</option>
            <option v-if="runtimeWorkspace === 'drill'" value="selected">数学严选题</option>
            <template v-else>
              <option value="core_selected">五科核心严选</option>
              <option value="circuit_selected">电路严选</option><option value="signal_selected">信号严选</option>
              <option value="analog_selected">模电严选</option><option value="digital_selected">数电严选</option>
              <option value="communication_selected">通信严选</option>
            </template>
          </template>
          <template v-else-if="kind === 'daily'"><option value="today">今天</option><option value="yesterday">昨天</option><option value="custom">指定日期</option></template>
          <template v-else><option value="recent7">最近 7 天</option><option value="previous7">上一个 7 天</option></template>
        </select>
      </label>
      <label v-if="kind === 'daily' && range === 'custom'">日期<input v-model="date" type="date"></label>
      <label class="note-choice"><input v-model="includeNotes" type="checkbox">包含当前 Note</label>
      <button type="button" :disabled="busy || (kind === 'daily' && range === 'custom' && !date)" @click="create">生成 7 天链接</button>
    </div>
    <p class="scope">将分享：{{ scopeDescription }}</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <div v-if="created" class="created-share">
      <p>到期时间：{{ new Date(created.expires_at).toLocaleString('zh-CN') }}</p>
      <input :value="created.url" readonly aria-label="AI 学习数据分享链接" @focus="($event.target as HTMLInputElement).select()">
      <div class="share-actions">
        <button type="button" @click="copy(created.url, 'link')">{{ copied === 'link' ? '已复制' : '复制链接' }}</button>
        <a :href="created.url" target="_blank" rel="noopener noreferrer">查看内容</a>
        <button type="button" @click="copy(prompt, 'prompt')">{{ copied === 'prompt' ? '已复制' : '复制给 ChatGPT 的提示词' }}</button>
        <button type="button" :disabled="busy" @click="copyMarkdown">{{ copied === 'markdown' ? '已复制 Markdown' : '复制 Markdown 全文' }}</button>
        <button type="button" :disabled="busy" @click="revoke(created.id)">立即撤销</button>
      </div>
      <label v-if="fallbackMarkdown">Safari 无法自动复制，请长按下面文本并选择“全选→复制”。
        <textarea :value="fallbackMarkdown" readonly rows="8" @focus="($event.target as HTMLTextAreaElement).select()" />
      </label>
    </div>
    <details v-if="records.length"><summary>有效分享（{{ records.length }}）</summary>
      <p>链接仅保存在创建它的浏览器。其他设备无法从服务器恢复明文链接，可撤销后重新生成。</p>
      <ul><li v-for="item in records" :key="item.id">{{ item.kind }} · 到期 {{ new Date(item.expires_at).toLocaleString('zh-CN') }} · Note {{ item.include_notes ? '已包含' : '未包含' }}
        <button v-if="savedLinks[item.id]" type="button" @click="copy(savedLinks[item.id], `record-${item.id}`)">复制链接</button>
        <a v-if="savedLinks[item.id]" :href="savedLinks[item.id]" target="_blank" rel="noopener noreferrer">查看</a>
        <button type="button" :disabled="busy" @click="revoke(item.id)">撤销</button></li></ul>
    </details>
  </details>
</template>

<style scoped>
.learning-share-panel { margin: 1rem 0; padding: 1rem; border: 1px solid var(--border-color, #b8c4d3); border-radius: 12px; background: var(--surface, #fff); }
.learning-share-panel summary { cursor: pointer; font-weight: 700; min-height: 44px; }
.learning-share-controls, .share-actions { display: flex; flex-wrap: wrap; gap: .7rem; align-items: end; }
.learning-share-controls label { display: grid; gap: .3rem; }
.learning-share-controls .note-choice { display: flex; align-items: center; min-height: 44px; }
.learning-share-panel button, .learning-share-panel select, .learning-share-panel input { min-height: 44px; }
.learning-share-panel button { padding: .5rem .8rem; }
.created-share input { box-sizing: border-box; width: 100%; }
.created-share textarea { box-sizing: border-box; width: 100%; min-height: 10rem; }
.scope { overflow-wrap: anywhere; opacity: .8; }
</style>
