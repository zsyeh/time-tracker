<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { EditPen, View } from '@element-plus/icons-vue'
import { api, patch, post } from '../lib/api'
import type { Page, ReviewTrend as ReviewTrendType, StudySession, StudySessionSummary } from '../types'
import MarkdownPreview from '../components/MarkdownPreview.vue'
import ReviewTrend from '../components/ReviewTrend.vue'

const loading = ref(false)
const router = useRouter()
const rows = ref<StudySessionSummary[]>([])
const total = ref(0)
const page = ref(1)
const expanded = ref<StudySession | null>(null)
const drawerOpen = ref(false)
const detailLoading = ref(false)
const editing = ref(false)
const reviewTrend = ref<ReviewTrendType | null>(null)
const filters = reactive({ search: '', subject: '', status: '' })
const edit = reactive({ title: '', details: '' })

function duration(minutes: number) { return minutes >= 60 ? `${Math.floor(minutes / 60)}h ${minutes % 60}m` : `${minutes}m` }
async function load() {
  loading.value = true
  const params = new URLSearchParams({ page: String(page.value) })
  if (filters.search) params.set('search', filters.search)
  if (filters.subject) params.set('subject', filters.subject)
  if (filters.status) params.set('status', filters.status)
  try { const data = await api<Page<StudySessionSummary>>(`/api/sessions/?${params}`); rows.value = data.results; total.value = data.count }
  catch (error) { ElMessage.error((error as Error).message) } finally { loading.value = false }
}
function openArticle(row: StudySessionSummary) {
  void router.push(`/sessions/${row.uuid}`)
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
function search() { page.value = 1; load() }
onMounted(load)
</script>

<template>
  <div class="view-stack">
    <section class="page-intro"><span class="eyebrow">SESSION ARCHIVE</span><h1>Sessions</h1><p>Search titles and open the full details only when needed.</p></section>
    <section class="panel filters"><el-input v-model="filters.search" clearable placeholder="Search title or details" @keyup.enter="search" /><el-select v-model="filters.subject" clearable placeholder="All subjects"><el-option label="Mathematics" value="math" /><el-option label="English" value="english" /><el-option label="Major" value="major" /><el-option label="Training" value="training" /></el-select><el-select v-model="filters.status" clearable placeholder="All statuses"><el-option label="Completed" value="completed" /><el-option label="Running" value="running" /></el-select><el-button type="primary" @click="search">Apply</el-button></section>
    <section class="panel history-panel" v-loading="loading">
      <el-empty v-if="!rows.length && !loading" description="No matching sessions" />
      <article v-for="row in rows" :key="row.uuid" class="history-row" @click="openArticle(row)">
        <time><b>{{ new Date(row.start_time).getDate().toString().padStart(2, '0') }}</b><span>{{ new Date(row.start_time).toLocaleDateString('en-US', { month: 'short' }) }}</span></time>
        <i :class="`subject-dot subject-${row.subject}`" />
        <div class="history-main"><strong>{{ row.title || (row.status === 'running' ? `${row.subject_label} session` : 'Untitled session') }}</strong><p>{{ row.status === 'running' ? 'Session in progress' : 'Markdown review available' }}</p><small>{{ row.subject_label }} · {{ new Date(row.start_time).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }) }} · {{ row.status }}</small></div>
        <div class="history-actions"><b v-if="row.status !== 'running'" class="duration-badge">{{ duration(row.duration_minutes) }}</b><b v-else class="running-badge">IN SESSION</b><button v-if="row.status === 'completed'" type="button" class="review-eye" :aria-label="`Review ${row.title || 'session'}`" @click.stop="inspect(row)"><el-icon><View /></el-icon><span>{{ row.review_count || 0 }}</span></button></div>
      </article>
      <el-pagination v-if="total > 20" v-model:current-page="page" layout="prev, pager, next" :total="total" :page-size="20" @current-change="load" />
    </section>
    <el-drawer v-model="drawerOpen" size="min(760px, 96vw)" class="review-drawer" destroy-on-close>
      <template #header><div class="dialog-title review-title"><div><span class="eyebrow">SESSION REVIEW</span><h2>{{ expanded?.title || 'Untitled session' }}</h2></div><div class="drawer-resource-actions"><el-button v-if="expanded" @click="drawerOpen = false; router.push(`/sessions/${expanded.uuid}`)">Open article</el-button><el-button v-if="expanded && !editing" :icon="EditPen" @click="editing = true">Edit</el-button></div></div></template>
      <div v-if="expanded" v-loading="detailLoading" class="session-detail-page review-page">
        <dl><div><dt>SUBJECT</dt><dd>{{ expanded.subject_label }}</dd></div><div><dt>DATE</dt><dd>{{ new Date(expanded.start_time).toLocaleDateString('en-CA') }}</dd></div><div><dt>DURATION</dt><dd>{{ duration(expanded.duration_minutes) }}</dd></div></dl>
        <ReviewTrend v-if="expanded.status === 'completed'" :trend="reviewTrend" :loading="detailLoading" />
        <el-form v-if="editing" label-position="top" class="simple-review review-editor"><el-form-item label="Title"><el-input v-model="edit.title" maxlength="500" show-word-limit /></el-form-item><el-form-item label="Markdown source"><el-input v-model="edit.details" type="textarea" :rows="20" placeholder="Paste Markdown or edit the source." /></el-form-item><MarkdownPreview :source="edit.details" /><div class="editor-actions"><el-button @click="editing = false">Cancel</el-button><el-button type="primary" @click="save">Save changes</el-button></div></el-form>
        <MarkdownPreview v-else :key="expanded.uuid" :source="expanded.details" default-open allow-fullscreen empty-text="No details were recorded for this session." />
      </div>
    </el-drawer>
  </div>
</template>
