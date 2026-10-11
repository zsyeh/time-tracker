<script setup lang="ts">
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Document, EditPen, Filter, Folder, FolderOpened, Operation, Search, View } from '@element-plus/icons-vue'
import { api, patch, post } from '../lib/api'
import type { Page, ReviewTrend as ReviewTrendType, StudySession, StudySessionSummary } from '../types'
import MarkdownPreview from '../components/MarkdownPreview.vue'
import ReviewTrend from '../components/ReviewTrend.vue'
import PageHeader from '../components/layout/PageHeader.vue'
import PageToolbar from '../components/layout/PageToolbar.vue'
import MenuPopover from '../components/ui/MenuPopover.vue'
import ToolbarChip from '../components/ui/ToolbarChip.vue'
import { useUiPreferences } from '../lib/uiPreferences'

const loading = ref(false)
const { language, t } = useUiPreferences()
const router = useRouter()
const route = useRoute()
const rows = ref<StudySessionSummary[]>([])
const total = ref(0)
const page = ref(1)
const expanded = ref<StudySession | null>(null)
const drawerOpen = ref(false)
const detailLoading = ref(false)
const editing = ref(false)
const reviewTrend = ref<ReviewTrendType | null>(null)
const filters = reactive({ search: '', subject: '', status: '' })
const includeEmpty = ref(false)
const collapsedDates = ref<Set<string>>(new Set())
const groupBy = ref<'date' | 'subject' | 'status' | 'none'>('date')
const sortBy = ref<'newest' | 'oldest' | 'duration'>('newest')
const density = ref<'compact' | 'comfortable'>('compact')
const properties = reactive({ tags: true, start: true, duration: true, efficiency: true })
const edit = reactive({ title: '', details: '' })
const subjects = computed(() => ({ math: t('mathematics'), english: t('english'), major: t('major'), training: t('training') }))
const activeSubjectLabel = computed(() => subjects.value[filters.subject as keyof typeof subjects.value] || filters.subject)
const sortedRows = computed(() => [...rows.value].sort((left, right) => {
  if (sortBy.value === 'duration') return right.credited_duration_minutes - left.credited_duration_minutes
  const delta = new Date(right.start_time).getTime() - new Date(left.start_time).getTime()
  return sortBy.value === 'oldest' ? -delta : delta
}))
const sessionGroups = computed(() => {
  const groups = new Map<string, StudySessionSummary[]>()
  for (const row of sortedRows.value) {
    const key = groupBy.value === 'date' ? localDateKey(row.start_time)
      : groupBy.value === 'subject' ? row.subject_label
        : groupBy.value === 'status' ? row.status
          : 'Sessions'
    groups.set(key, [...(groups.get(key) || []), row])
  }
  return [...groups.entries()].map(([key, sessions]) => ({
    key,
    label: groupBy.value === 'date' ? dateFolderLabel(sessions[0].start_time) : key,
    sessions,
  }))
})

function duration(minutes: number) { return minutes >= 60 ? `${Math.floor(minutes / 60)}h ${minutes % 60}m` : `${minutes}m` }
function efficiency(session: StudySessionSummary) {
  return `${session.efficiency_grade} · ×${session.efficiency_coefficient.toFixed(2)}`
}
function localDateKey(value: string) {
  const date = new Date(value)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}
function dateFolderLabel(value: string) {
  const date = new Date(value)
  const today = new Date()
  const yesterday = new Date(today)
  yesterday.setDate(today.getDate() - 1)
  const key = localDateKey(value)
  const dateText = date.toLocaleDateString(language.value, { year: 'numeric', month: 'long', day: 'numeric', weekday: 'short' })
  if (key === localDateKey(today.toISOString())) return `${t('today')} · ${dateText}`
  if (key === localDateKey(yesterday.toISOString())) return `Yesterday · ${dateText}`
  return dateText
}
async function load() {
  loading.value = true
  const params = new URLSearchParams({ page: String(page.value), articles: '1' })
  if (!includeEmpty.value) params.set('has_details', '1')
  if (filters.search) params.set('search', filters.search)
  if (filters.subject) params.set('subject', filters.subject)
  if (filters.status) params.set('status', filters.status)
  try {
    const data = await api<Page<StudySessionSummary>>(`/api/sessions/?${params}`)
    rows.value = data.results
    total.value = data.count
    await restoreScrollPosition()
  }
  catch (error) { ElMessage.error((error as Error).message) } finally { loading.value = false }
}
function openArticle(row: StudySessionSummary) {
  sessionStorage.setItem('timer.sessions.return.v1', JSON.stringify({ path: route.fullPath, scrollY: window.scrollY }))
  void router.push({ path: `/sessions/${row.uuid}`, query: { returnTo: route.fullPath } })
}
async function inspect(row: StudySessionSummary) {
  drawerOpen.value = true
  detailLoading.value = true
  editing.value = false
  expanded.value = null
  reviewTrend.value = null
  try {
    const [session, trend] = row.status === 'completed'
      ? await Promise.all([
          api<StudySession>(`/api/sessions/${row.uuid}/`),
          post<ReviewTrendType>(`/api/sessions/${row.uuid}/reviews/`),
        ])
      : [await api<StudySession>(`/api/sessions/${row.uuid}/`), null]
    if (trend) {
      session.review_count = trend.total
      session.last_reviewed_at = trend.last_reviewed_at
    }
    expanded.value = session
    reviewTrend.value = trend
    Object.assign(edit, { title: session.title || '', details: session.details })
    const listItem = rows.value.find((item) => item.uuid === row.uuid)
    if (listItem && trend) { listItem.review_count = trend.total; listItem.last_reviewed_at = trend.last_reviewed_at }
  } catch (error) { ElMessage.error((error as Error).message) }
  finally { detailLoading.value = false }
}
async function save() { if (!expanded.value) return; try { expanded.value = await patch(`/api/sessions/${expanded.value.uuid}/`, edit); editing.value = false; ElMessage.success('Session updated'); await load() } catch (error) { ElMessage.error((error as Error).message) } }
function routeQuery() {
  const query: Record<string, string> = {}
  if (page.value > 1) query.page = String(page.value)
  if (filters.search) query.search = filters.search
  if (filters.subject) query.subject = filters.subject
  if (filters.status) query.status = filters.status
  if (includeEmpty.value) query.include_empty = '1'
  return query
}
function applyFilters(resetPage = true) {
  if (resetPage) page.value = 1
  const target = { path: '/sessions', query: routeQuery() }
  if (router.resolve(target).fullPath === route.fullPath) void load()
  else void router.replace(target)
}
function hydrateFromRoute() {
  const requestedPage = Number.parseInt(String(route.query.page || '1'), 10)
  page.value = Number.isFinite(requestedPage) && requestedPage > 0 ? requestedPage : 1
  filters.search = typeof route.query.search === 'string' ? route.query.search : ''
  filters.subject = ['math', 'english', 'major', 'training'].includes(String(route.query.subject)) ? String(route.query.subject) : ''
  filters.status = ['completed', 'running', 'abandoned'].includes(String(route.query.status)) ? String(route.query.status) : ''
  includeEmpty.value = route.query.include_empty === '1'
}
async function restoreScrollPosition() {
  const raw = sessionStorage.getItem('timer.sessions.return.v1')
  if (!raw) return
  try {
    const saved = JSON.parse(raw) as { path?: string; scrollY?: number }
    if (saved.path !== route.fullPath || typeof saved.scrollY !== 'number') return
    sessionStorage.removeItem('timer.sessions.return.v1')
    await nextTick()
    requestAnimationFrame(() => window.scrollTo({ top: saved.scrollY || 0, behavior: 'auto' }))
  } catch { sessionStorage.removeItem('timer.sessions.return.v1') }
}
function toggleDate(key: string) {
  const next = new Set(collapsedDates.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  collapsedDates.value = next
}
watch(() => route.fullPath, () => { hydrateFromRoute(); void load() }, { immediate: true })
</script>

<template>
  <div class="workspace-view sessions-view">
    <PageHeader :context="t('workspace')" :title="t('sessions')" :metadata="t('records', { count: total })" />
    <PageToolbar label="Session filters and display">
      <ToolbarChip label="Markdown only" :active="!includeEmpty" @click="includeEmpty = !includeEmpty; applyFilters()" />
      <ToolbarChip :label="t('allSessions')" :active="!filters.subject && !filters.status" @click="filters.subject = ''; filters.status = ''; applyFilters()" />
      <ToolbarChip v-if="filters.subject" :label="activeSubjectLabel" active @click="filters.subject = ''; applyFilters()"><template #suffix><span aria-hidden="true">×</span></template></ToolbarChip>
      <ToolbarChip v-if="filters.status" :label="filters.status" active @click="filters.status = ''; applyFilters()"><template #suffix><span aria-hidden="true">×</span></template></ToolbarChip>
      <template #actions>
        <label class="toolbar-search"><el-icon><Search /></el-icon><input v-model="filters.search" type="search" :placeholder="t('searchSessions')" :aria-label="t('searchSessions')" @keyup.enter="applyFilters()" /><button v-if="filters.search" type="button" aria-label="Clear search" @click="filters.search = ''; applyFilters()">×</button></label>
        <MenuPopover :label="t('filter')" align="end">
          <template #trigger><el-icon><Filter /></el-icon><span>{{ t('filter') }}</span><b v-if="filters.subject || filters.status" class="control-count">{{ Number(Boolean(filters.subject)) + Number(Boolean(filters.status)) }}</b></template>
          <div class="menu-section"><span>Content</span><label class="menu-toggle"><span>Only sessions with Markdown</span><el-switch :model-value="!includeEmpty" size="small" @change="includeEmpty = !$event; applyFilters()" /></label></div>
          <div class="menu-section"><span>Subject</span><button type="button" class="menu-option" :class="{ selected: !filters.subject }" @click="filters.subject = ''; applyFilters()"><i />All subjects</button><button v-for="(label, key) in subjects" :key="key" type="button" class="menu-option" :class="{ selected: filters.subject === key }" @click="filters.subject = key; applyFilters()"><i />{{ label }}</button></div>
          <div class="menu-section"><span>Status</span><button type="button" class="menu-option" :class="{ selected: !filters.status }" @click="filters.status = ''; applyFilters()"><i />All statuses</button><button v-for="option in ['completed', 'running']" :key="option" type="button" class="menu-option" :class="{ selected: filters.status === option }" @click="filters.status = option; applyFilters()"><i />{{ option }}</button></div>
        </MenuPopover>
        <MenuPopover :label="t('properties')" align="end">
          <template #trigger><el-icon><View /></el-icon><span>{{ t('display') }}</span></template>
          <div class="menu-section"><span>Visible properties</span><label class="menu-toggle"><span>Tags</span><el-switch v-model="properties.tags" size="small" /></label><label class="menu-toggle"><span>Start time</span><el-switch v-model="properties.start" size="small" /></label><label class="menu-toggle"><span>Duration</span><el-switch v-model="properties.duration" size="small" /></label><label class="menu-toggle"><span>Efficiency</span><el-switch v-model="properties.efficiency" size="small" /></label></div>
        </MenuPopover>
        <MenuPopover :label="t('view')" align="end">
          <template #trigger><el-icon><Operation /></el-icon><span>{{ t('view') }}</span></template>
          <div class="menu-section"><span>Group by</span><button v-for="option in (['date', 'subject', 'status', 'none'] as const)" :key="option" type="button" class="menu-option" :class="{ selected: groupBy === option }" @click="groupBy = option"><i />{{ option }}</button></div>
          <div class="menu-section"><span>Sort current page</span><button v-for="option in (['newest', 'oldest', 'duration'] as const)" :key="option" type="button" class="menu-option" :class="{ selected: sortBy === option }" @click="sortBy = option"><i />{{ option }}</button></div>
          <div class="menu-section"><span>Density</span><button v-for="option in (['compact', 'comfortable'] as const)" :key="option" type="button" class="menu-option" :class="{ selected: density === option }" @click="density = option"><i />{{ option }}</button></div>
        </MenuPopover>
      </template>
    </PageToolbar>
    <section class="history-panel" :class="`density-${density}`" v-loading="loading">
      <el-empty v-if="!rows.length && !loading" :description="includeEmpty ? 'No matching sessions' : 'No sessions with Markdown on this page'" />
      <section v-for="group in sessionGroups" :key="group.key" class="resource-group session-group" :class="{ collapsed: collapsedDates.has(group.key) }">
        <button v-if="groupBy === 'date'" type="button" class="resource-group-header date-folder" :aria-expanded="!collapsedDates.has(group.key)" @click="toggleDate(group.key)"><div><el-icon><Folder v-if="collapsedDates.has(group.key)" /><FolderOpened v-else /></el-icon><strong>{{ group.label }}</strong><b>{{ group.sessions.length }}</b></div><span>{{ collapsedDates.has(group.key) ? 'Open folder' : 'Close folder' }}</span></button>
        <header v-else class="resource-group-header"><div><strong>{{ group.label }}</strong><b>{{ group.sessions.length }}</b></div><span>{{ groupBy === 'none' ? 'Current page' : `Grouped by ${groupBy}` }}</span></header>
        <template v-if="!collapsedDates.has(group.key) || groupBy !== 'date'">
        <article v-for="row in group.sessions" :key="row.uuid" class="history-row" @click="openArticle(row)">
          <i :class="`subject-dot subject-${row.subject}`" />
          <div class="history-main"><strong><el-icon v-if="row.details_preview" class="article-indicator"><Document /></el-icon>{{ row.title || (row.status === 'running' ? `${row.subject_label} session` : 'Untitled session') }}</strong><p class="session-excerpt">{{ row.details_preview || row.task_path || (row.status === 'running' ? 'Session in progress' : 'No Markdown body') }}</p><small>{{ row.subject_label }} · {{ row.status }}<span v-if="properties.tags && row.tags.length"> · {{ row.tags.map((tag) => `#${tag.name}`).join(' ') }}</span></small></div>
          <time v-if="properties.start" class="session-start">{{ new Date(row.start_time).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }) }}</time>
          <div class="history-actions"><span v-if="properties.duration && row.status !== 'running'" class="duration-badge"><b>{{ duration(row.credited_duration_minutes) }}</b><small v-if="properties.efficiency">{{ efficiency(row) }}</small></span><b v-else-if="row.status === 'running'" class="running-badge">IN SESSION</b><button v-if="row.status === 'completed'" type="button" class="review-eye" :aria-label="`Review ${row.title || 'session'}`" @click.stop="inspect(row)"><el-icon><View /></el-icon><span>{{ row.review_count || 0 }}</span></button></div>
        </article>
        </template>
      </section>
      <el-pagination v-if="total > 20" v-model:current-page="page" layout="prev, pager, next" :total="total" :page-size="20" @current-change="applyFilters(false)" />
    </section>
    <el-drawer v-model="drawerOpen" size="min(760px, 96vw)" class="review-drawer" destroy-on-close>
      <template #header><div class="dialog-title review-title"><div><span class="eyebrow">SESSION REVIEW</span><h2>{{ expanded?.title || 'Untitled session' }}</h2></div><div class="drawer-resource-actions"><el-button v-if="expanded" @click="drawerOpen = false; openArticle(expanded)">Open article</el-button><el-button v-if="expanded && !editing" :icon="EditPen" @click="editing = true">Edit</el-button></div></div></template>
      <div v-if="expanded" v-loading="detailLoading" class="session-detail-page review-page">
        <dl><div><dt>SUBJECT</dt><dd>{{ expanded.subject_label }}</dd></div><div><dt>TASK</dt><dd>{{ expanded.task_path || '—' }}</dd></div><div><dt>DATE</dt><dd>{{ new Date(expanded.start_time).toLocaleDateString('en-CA') }}</dd></div><div><dt>CREDITED</dt><dd>{{ duration(expanded.credited_duration_minutes) }}</dd></div><div><dt>ACTUAL</dt><dd>{{ duration(expanded.duration_minutes) }}</dd></div><div><dt>EFFICIENCY</dt><dd>{{ efficiency(expanded) }}</dd></div></dl>
        <div v-if="expanded.tags.length" class="completion-tags"><span>TAGS</span><button v-for="tag in expanded.tags" :key="tag.id" type="button" class="selected">#{{ tag.name }}</button></div>
        <ReviewTrend v-if="expanded.status === 'completed'" :trend="reviewTrend" :loading="detailLoading" />
        <el-form v-if="editing" label-position="top" class="simple-review review-editor"><el-form-item label="Title"><el-input v-model="edit.title" maxlength="500" show-word-limit /></el-form-item><el-form-item label="Markdown source"><el-input v-model="edit.details" type="textarea" :rows="20" placeholder="Paste Markdown or edit the source." /></el-form-item><MarkdownPreview :source="edit.details" /><div class="editor-actions"><el-button @click="editing = false">Cancel</el-button><el-button type="primary" @click="save">Save changes</el-button></div></el-form>
        <MarkdownPreview v-else :key="expanded.uuid" :source="expanded.details" default-open allow-fullscreen empty-text="No details were recorded for this session." />
      </div>
    </el-drawer>
  </div>
</template>
