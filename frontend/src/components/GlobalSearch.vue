<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { api } from '../lib/api'
import type { GlobalSearchResponse, GlobalSearchResult, Issue, StudySession } from '../types'
import MarkdownPreview from './MarkdownPreview.vue'

const router = useRouter()
const searchOpen = ref(false)
const detailOpen = ref(false)
const query = ref('')
const results = ref<GlobalSearchResult[]>([])
const loading = ref(false)
const detailLoading = ref(false)
const selectedIssue = ref<Issue | null>(null)
const inputRef = ref<{ focus: () => void } | null>(null)
const cache = new Map<string, GlobalSearchResult[]>()
const subjects = { math: 'Mathematics', english: 'English', major: 'Major', training: 'Training' }
let timer: ReturnType<typeof setTimeout> | undefined
let requestVersion = 0

function open() {
  searchOpen.value = true
  nextTick(() => inputRef.value?.focus())
}

function close() { searchOpen.value = false }

async function runSearch() {
  const keyword = query.value.trim()
  const version = ++requestVersion
  if (!keyword) { results.value = []; loading.value = false; return }
  const cacheKey = keyword.toLocaleLowerCase()
  const cached = cache.get(cacheKey)
  if (cached) { results.value = cached; loading.value = false; return }
  loading.value = true
  try {
    const response = await api<GlobalSearchResponse>(`/api/search/?q=${encodeURIComponent(keyword)}&limit=18`)
    if (version !== requestVersion) return
    results.value = response.results
    cache.set(cacheKey, response.results)
    if (cache.size > 20) cache.delete(cache.keys().next().value as string)
  } catch (error) {
    if (version === requestVersion) ElMessage.error((error as Error).message)
  } finally {
    if (version === requestVersion) loading.value = false
  }
}

watch(query, () => {
  if (timer) clearTimeout(timer)
  timer = setTimeout(runSearch, 220)
})

function textSegments(text: string) {
  const needle = query.value.trim()
  if (!needle) return [{ text, match: false }]
  const source = text || ''
  const lower = source.toLocaleLowerCase()
  const target = needle.toLocaleLowerCase()
  const segments: Array<{ text: string; match: boolean }> = []
  let cursor = 0
  let index = lower.indexOf(target)
  while (index >= 0) {
    if (index > cursor) segments.push({ text: source.slice(cursor, index), match: false })
    segments.push({ text: source.slice(index, index + needle.length), match: true })
    cursor = index + needle.length
    index = lower.indexOf(target, cursor)
  }
  if (cursor < source.length) segments.push({ text: source.slice(cursor), match: false })
  return segments.length ? segments : [{ text: source, match: false }]
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
})
defineExpose({ open })
</script>

<template>
  <button type="button" class="global-search-trigger" aria-label="Open global search" @click="open">
    <el-icon><Search /></el-icon><span>Search everything</span><kbd>⌘ K</kbd>
  </button>

  <el-dialog v-model="searchOpen" class="global-search-dialog" width="min(720px, 94vw)" :show-close="false" append-to-body @opened="inputRef?.focus()">
    <template #header>
      <div class="global-search-input">
        <el-icon><Search /></el-icon>
        <el-input ref="inputRef" v-model="query" clearable placeholder="Search titles, Markdown details, and issues" />
        <kbd>ESC</kbd>
      </div>
    </template>
    <div class="global-search-results" v-loading="loading">
      <div v-if="!query.trim()" class="search-empty-state"><span>GLOBAL TEXT SEARCH</span><p>Type a keyword. Results include sessions and Issues.</p></div>
      <el-empty v-else-if="!loading && !results.length" description="No matching text" :image-size="62" />
      <template v-else>
        <button v-for="result in results" :key="`${result.kind}-${result.record_id}`" type="button" class="global-result" @click="openResult(result)">
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
