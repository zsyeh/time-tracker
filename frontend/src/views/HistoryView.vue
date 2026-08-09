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
async function save() { if (!expanded.value) return; try { expanded.value = await patch(`/api/sessions/${expanded.value.id}/`, edit); editing.value = false; ElMessage.success('记录已更新'); await load() } catch (error) { ElMessage.error((error as Error).message) } }
function search() { page.value = 1; load() }
onMounted(load)
</script>

<template>
  <div class="view-stack">
    <section class="page-intro"><span class="eyebrow">SESSION ARCHIVE</span><h1>学习记录</h1><p>搜索、筛选和复盘每一次学习，原始总结始终完整保留。</p></section>
    <section class="panel filters"><el-input v-model="filters.search" clearable placeholder="搜索主题、总结、突破或问题" @keyup.enter="search" /><el-select v-model="filters.subject" clearable placeholder="全部科目"><el-option label="数学" value="math" /><el-option label="英语" value="english" /><el-option label="专业课" value="major" /><el-option label="训练" value="training" /></el-select><el-select v-model="filters.status" clearable placeholder="全部状态"><el-option label="已完成" value="completed" /><el-option label="进行中" value="running" /><el-option label="已放弃" value="abandoned" /></el-select><el-button type="primary" @click="search">查询</el-button></section>
    <section class="panel history-panel" v-loading="loading">
      <el-empty v-if="!rows.length && !loading" description="没有符合条件的记录" />
      <article v-for="row in rows" :key="row.id" class="history-row" @click="inspect(row)">
        <time><b>{{ new Date(row.start_time).getDate().toString().padStart(2, '0') }}</b><span>{{ new Date(row.start_time).toLocaleDateString('zh-CN', { month: 'short' }) }}</span></time>
        <i :class="`subject-dot subject-${row.subject}`" />
        <div class="history-main"><strong>{{ row.subject_label }} · {{ row.topic || row.chapter || '未命名学习' }}</strong><p>{{ row.note || (row.status === 'running' ? '正在学习中…' : '暂无总结') }}</p><small>{{ new Date(row.start_time).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) }} · {{ row.status }}</small></div>
        <b v-if="row.status !== 'running'" class="duration-badge">{{ duration(row.duration_minutes) }}</b>
        <b v-else class="running-badge">IN SESSION</b>
      </article>
      <el-pagination v-if="total > 20" v-model:current-page="page" layout="prev, pager, next" :total="total" :page-size="20" @current-change="load" />
    </section>
    <el-drawer v-model="editing" title="编辑学习复盘" size="min(560px, 94vw)">
      <el-form label-position="top"><div class="form-pair"><el-form-item label="章节"><el-input v-model="edit.chapter" /></el-form-item><el-form-item label="主题"><el-input v-model="edit.topic" /></el-form-item></div><el-form-item label="学习总结"><el-input v-model="edit.note" type="textarea" :rows="5" /></el-form-item><el-form-item label="突破"><el-input v-model="edit.breakthrough" type="textarea" :rows="3" /></el-form-item><el-form-item label="问题"><el-input v-model="edit.problems" type="textarea" :rows="3" /></el-form-item><el-form-item label="下一步"><el-input v-model="edit.next_action" type="textarea" :rows="3" /></el-form-item><el-button type="primary" @click="save">保存修改</el-button></el-form>
    </el-drawer>
  </div>
</template>
