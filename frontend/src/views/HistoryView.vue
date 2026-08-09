<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api, patch } from '../lib/api'
import type { Page, StudySession } from '../types'

const loading = ref(false)
const rows = ref<StudySession[]>([])
const total = ref(0)
const page = ref(1)
const expanded = ref<StudySession | null>(null)
const editing = ref(false)
const filters = reactive({ search: '', subject: '', status: '' })
const edit = reactive({ chapter: '', topic: '', note: '', breakthrough: '', problems: '', next_action: '' })

function duration(minutes: number) { return minutes >= 60 ? `${Math.floor(minutes / 60)}h ${minutes % 60}m` : `${minutes}m` }
async function load() {
  loading.value = true
  const params = new URLSearchParams({ page: String(page.value) })
  if (filters.search) params.set('search', filters.search)
  if (filters.subject) params.set('subject', filters.subject)
  if (filters.status) params.set('status', filters.status)
  try { const data = await api<Page<StudySession>>(`/api/sessions/?${params}`); rows.value = data.results; total.value = data.count }
  catch (error) { ElMessage.error((error as Error).message) } finally { loading.value = false }
}
function inspect(row: StudySession) { expanded.value = row; Object.assign(edit, { chapter: row.chapter, topic: row.topic, note: row.note, breakthrough: row.breakthrough, problems: row.problems, next_action: row.next_action }); editing.value = true }
async function save() { if (!expanded.value) return; try { expanded.value = await patch(`/api/sessions/${expanded.value.id}/`, edit); editing.value = false; ElMessage.success('Session updated'); await load() } catch (error) { ElMessage.error((error as Error).message) } }
function search() { page.value = 1; load() }
onMounted(load)
</script>

<template>
  <div class="view-stack">
    <section class="page-intro"><span class="eyebrow">SESSION ARCHIVE</span><h1>Sessions</h1><p>Search completed reviews and inspect the underlying session record.</p></section>
    <section class="panel filters"><el-input v-model="filters.search" clearable placeholder="Search topic, summary, breakthrough, or problem" @keyup.enter="search" /><el-select v-model="filters.subject" clearable placeholder="All subjects"><el-option label="Mathematics" value="math" /><el-option label="English" value="english" /><el-option label="Major" value="major" /><el-option label="Training" value="training" /></el-select><el-select v-model="filters.status" clearable placeholder="All statuses"><el-option label="Completed" value="completed" /><el-option label="Running" value="running" /></el-select><el-button type="primary" @click="search">Apply</el-button></section>
    <section class="panel history-panel" v-loading="loading">
      <el-empty v-if="!rows.length && !loading" description="No matching sessions" />
      <article v-for="row in rows" :key="row.id" class="history-row" @click="inspect(row)">
        <time><b>{{ new Date(row.start_time).getDate().toString().padStart(2, '0') }}</b><span>{{ new Date(row.start_time).toLocaleDateString('en-US', { month: 'short' }) }}</span></time>
        <i :class="`subject-dot subject-${row.subject}`" />
        <div class="history-main"><strong>{{ row.subject_label }} · {{ row.topic || row.chapter || 'Untitled session' }}</strong><p>{{ row.note || (row.status === 'running' ? 'Session in progress' : 'No summary') }}</p><small>{{ new Date(row.start_time).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }) }} · {{ row.status }}</small></div>
        <b v-if="row.status !== 'running'" class="duration-badge">{{ duration(row.duration_minutes) }}</b>
        <b v-else class="running-badge">IN SESSION</b>
      </article>
      <el-pagination v-if="total > 20" v-model:current-page="page" layout="prev, pager, next" :total="total" :page-size="20" @current-change="load" />
    </section>
    <el-drawer v-model="editing" title="Edit session review" size="min(560px, 94vw)">
      <el-form label-position="top"><div class="form-pair"><el-form-item label="Chapter"><el-input v-model="edit.chapter" /></el-form-item><el-form-item label="Topic"><el-input v-model="edit.topic" /></el-form-item></div><el-form-item label="Summary"><el-input v-model="edit.note" type="textarea" :rows="5" /></el-form-item><el-form-item label="Breakthrough"><el-input v-model="edit.breakthrough" type="textarea" :rows="3" /></el-form-item><el-form-item label="Problems"><el-input v-model="edit.problems" type="textarea" :rows="3" /></el-form-item><el-form-item label="Next action"><el-input v-model="edit.next_action" type="textarea" :rows="3" /></el-form-item><el-button type="primary" @click="save">Save changes</el-button></el-form>
    </el-drawer>
  </div>
</template>
