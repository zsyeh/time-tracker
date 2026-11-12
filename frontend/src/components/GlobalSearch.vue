<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { api } from '../lib/api'
import type { GlobalSearchResponse, GlobalSearchResult, Issue, StudySession } from '../types'
import MarkdownPreview from './MarkdownPreview.vue'
import { useUiPreferences } from '../lib/uiPreferences'
import { learningUserId } from '../../shared/foregroundTimer'

const router = useRouter()
const { t } = useUiPreferences()
const searchOpen = ref(false)
const detailOpen = ref(false)
const query = ref('')
const results = ref<GlobalSearchResult[]>([])
const loading = ref(false)
const detailLoading = ref(false)
const selectedIssue = ref<Issue | null>(null)
const inputRef = ref<{ focus: () => void } | null>(null)
const cache = new Map<string, GlobalSearchResult[]>()
const subjects = { math: 'Mathematics', english: 'English', major: 'Major', training: 'Politics' }
let timer: ReturnType<typeof setTimeout> | undefined
let requestVersion = 0
let requestController: AbortController | null = null
const composing = ref(false)
const activeResult = ref(-1)

function open() {
  searchOpen.value = true
  nextTick(() => inputRef.value?.focus())
}

function close() { searchOpen.value = false; requestController?.abort(); requestVersion += 1; loading.value = false }

async function runSearch() {
  if (composing.value || !searchOpen.value) return
  requestController?.abort()
  requestController = new AbortController()
  const keyword = query.value.trim()
  const version = ++requestVersion
  if (!keyword) { results.value = []; loading.value = false; return }
  const cacheKey = `${learningUserId}:${keyword.toLocaleLowerCase()}`
  const cached = cache.get(cacheKey)
  if (cached) { results.value = cached; loading.value = false; return }
  loading.value = true
  try {
    const response = await api<GlobalSearchResponse>(`/api/search/?q=${encodeURIComponent(keyword)}&limit=18`, { signal: requestController.signal })
    if (version !== requestVersion) return
    results.value = response.results
    cache.set(cacheKey, response.results)
    if (cache.size > 20) cache.delete(cache.keys().next().value as string)
  } catch (error) {
    if (version === requestVersion && (error as Error).name !== 'AbortError') ElMessage.error((error as Error).message)
  } finally {
    if (version === requestVersion) loading.value = false
  }
}

function scheduleSearch() {
  if (timer) clearTimeout(timer)
  requestController?.abort()
  requestVersion += 1
  activeResult.value = -1
  loading.value = false
  if (!composing.value) timer = setTimeout(runSearch, 250)
}
watch(query, scheduleSearch, { flush: 'sync' })
watch(searchOpen, (opened) => { if (!opened) close(); else void runSearch() })
function startComposition() { composing.value = true; if (timer) clearTimeout(timer); requestController?.abort(); requestVersion += 1 }
function endComposition() { composing.value = false; scheduleSearch() }
function inputKeydown(event: KeyboardEvent) {
  if (composing.value || event.isComposing || event.keyCode === 229) return
  if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    if (!results.value.length) return
    event.preventDefault()
    activeResult.value = (activeResult.value + (event.key === 'ArrowDown' ? 1 : -1) + results.value.length) % results.value.length
  } else if (event.key === 'Enter') {
    event.preventDefault()
    const result = results.value[activeResult.value]
    if (result) void openResult(result)
    else { if (timer) clearTimeout(timer); void runSearch() }
  }
}

function textSegments(text: string) {
  const needle = query.value.trim()
  const source = Array.from(text || '')
  const width = Array.from(needle).length
  if (!width) return [{ text: text || '', match: false }]
  const target = needle.toLocaleLowerCase()
  const segments: Array<{ text: string; match: boolean }> = []
  let cursor = 0
  let pending = ''
  while (cursor < source.length) {
    const part = source.slice(cursor, cursor + width).join('')
    if (part.toLocaleLowerCase() === target) {
      if (pending) { segments.push({ text: pending, match: false }); pending = '' }
      segments.push({ text: part, match: true }); cursor += width
    } else { pending += source[cursor]; cursor += 1 }
  }
  if (pending) segments.push({ text: pending, match: false })
  return segments.length ? segments : [{ text: text || '', match: false }]
}

async function openResult(result: GlobalSearchResult) {
  if (result.kind === 'session') {
    searchOpen.value = false
    if (result.session_uuid) {
      await router.push(`/sessions/${result.session_uuid}`)
      return
    }
    const session = await api<StudySession>(`/api/sessions/${result.record_id}/`)
    await router.push(`/sessions/${session.uuid}`)
    return
  }
  selectedIssue.value = null
  searchOpen.value = false
  detailOpen.value = true
  detailLoading.value = true
  try {
    selectedIssue.value = await api<Issue>(`/api/issues/${result.record_id}/`)
  } catch (error) {
    ElMessage.error((error as Error).message)
  } finally {
    detailLoading.value = false
  }
}

function showIssues() {
  detailOpen.value = false
  void router.push('/issues')
}

function keyboard(event: KeyboardEvent) {
  if ((event.metaKey || event.ctrlKey) && event.key.toLocaleLowerCase() === 'k') {
    event.preventDefault()
    searchOpen.value ? close() : open()
  }
}

onMounted(() => window.addEventListener('keydown', keyboard))
onBeforeUnmount(() => {
  window.removeEventListener('keydown', keyboard)
  if (timer) clearTimeout(timer)
  requestController?.abort()
  requestVersion += 1
})
defineExpose({ open })
</script>

<template>
  <button type="button" class="global-search-trigger" :aria-label="t('search')" @click="open">
    <el-icon><Search /></el-icon><span>{{ t('search') }}</span><kbd>⌘K</kbd>
  </button>

  <el-dialog v-model="searchOpen" class="global-search-dialog" width="min(720px, 94vw)" :show-close="false" append-to-body @opened="inputRef?.focus()">
    <template #header>
      <div class="global-search-input">
        <el-icon><Search /></el-icon>
        <el-input ref="inputRef" v-model="query" clearable placeholder="Search titles, study notes, and issues" role="combobox" aria-controls="global-search-options" :aria-expanded="Boolean(results.length)" :aria-activedescendant="activeResult >= 0 ? `global-search-result-${activeResult}` : undefined" @compositionstart="startComposition" @compositionend="endComposition" @keydown="inputKeydown" />
        <kbd>ESC</kbd>
      </div>
    </template>
    <div id="global-search-options" class="global-search-results" role="listbox" aria-label="Search results" :aria-busy="loading" v-loading="loading">
      <div v-if="!query.trim()" class="search-empty-state"><p>Search your sessions and issues.</p></div>
      <el-empty v-else-if="!loading && !results.length" description="No matching text" :image-size="62" />
      <template v-else>
        <button v-for="(result, index) in results" :id="`global-search-result-${index}`" role="option" :aria-selected="activeResult === index" :key="`${result.kind}-${result.record_id}`" type="button" class="global-result" @click="openResult(result)">
          <span class="result-kind">{{ result.kind }}</span>
          <span class="result-copy"><strong><template v-for="(part, index) in textSegments(result.title)" :key="index"><mark v-if="part.match">{{ part.text }}</mark><template v-else>{{ part.text }}</template></template></strong><small><template v-for="(part, index) in textSegments(result.snippet)" :key="index"><mark v-if="part.match">{{ part.text }}</mark><template v-else>{{ part.text }}</template></template></small></span>
          <span class="result-meta">{{ result.subject_label }}<time>{{ new Date(result.occurred_at).toLocaleDateString('en-CA') }}</time></span>
        </button>
      </template>
    </div>
  </el-dialog>

  <el-drawer v-model="detailOpen" append-to-body size="min(720px, 94vw)" class="global-detail-drawer">
    <template #header>
      <div class="dialog-title"><div><span class="eyebrow">GLOBAL SEARCH / ISSUE</span><h2>{{ selectedIssue?.topic || 'Search result' }}</h2></div></div>
    </template>
    <div v-loading="detailLoading" class="global-result-detail">
      <template v-if="selectedIssue">
        <div class="detail-meta"><span>{{ subjects[selectedIssue.subject] }}</span><b>{{ selectedIssue.resolved ? 'RESOLVED' : 'OPEN' }}</b></div>
        <section class="issue-search-section"><span>DESCRIPTION</span><MarkdownPreview :key="`description-${selectedIssue.id}`" :source="selectedIssue.description" default-open allow-fullscreen /></section>
        <section v-if="selectedIssue.solution" class="issue-search-section"><span>SOLUTION</span><MarkdownPreview :key="`solution-${selectedIssue.id}`" :source="selectedIssue.solution" default-open allow-fullscreen /></section>
        <el-button type="primary" @click="showIssues">Open Issues</el-button>
      </template>
    </div>
  </el-drawer>
</template>

<style scoped>
.global-search-trigger { border:0; background:transparent; box-shadow:none; }
.global-result { border:0; border-radius:4px; background:transparent; min-height:64px; }
.global-result[aria-selected=true] { background:var(--surface-selected); }
.global-result mark { background:var(--accent-soft); color:var(--accent-ink); }
.result-copy { min-width:0; } .result-copy strong,.result-copy small { overflow-wrap:anywhere; }
.search-empty-state { padding:24px; color:var(--text-secondary); font-size:14px; }
</style>
