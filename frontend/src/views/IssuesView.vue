<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api, patch, post, remove } from '../lib/api'
import type { Issue, Page } from '../types'

const rows = ref<Issue[]>([])
const open = ref(false)
const loading = ref(false)
const form = reactive({ subject: 'math', topic: '', issue_type: 'concept_error', description: '', solution: '', repeat_count: 1 })
const labels: Record<string, string> = {
  concept_error: 'Concept error', calculation_error: 'Calculation error', recognition_error: 'Recognition error',
  memory_error: 'Memory error', speed_problem: 'Speed problem', careless_error: 'Careless error', strategy_problem: 'Strategy problem',
}
const subjects = { math: 'Mathematics', english: 'English', major: 'Major', training: 'Training' }

async function load() {
  loading.value = true
  try { rows.value = (await api<Page<Issue>>('/api/issues/')).results }
  catch (error) { ElMessage.error((error as Error).message) }
  finally { loading.value = false }
}
async function create() {
  try {
    await post('/api/issues/', form)
    open.value = false
    Object.assign(form, { topic: '', description: '', solution: '', repeat_count: 1 })
    await load()
    ElMessage.success('Issue recorded')
  } catch (error) { ElMessage.error((error as Error).message) }
}
async function toggle(row: Issue) { await patch(`/api/issues/${row.id}/`, { resolved: !row.resolved }); await load() }
async function drop(row: Issue) { await remove(`/api/issues/${row.id}/`); await load() }
onMounted(load)
</script>

<template>
  <div class="view-stack">
    <section class="page-intro action-intro">
      <div><span class="eyebrow">ISSUE ANALYSIS</span><h1>Issues</h1><p>Track recurring errors, their resolution, and repeat frequency.</p></div>
      <el-button type="primary" @click="open = true">New issue</el-button>
    </section>
    <section class="panel issue-board" v-loading="loading">
      <div class="board-heading"><span>OPEN {{ rows.filter(row => !row.resolved).length }}</span><span>RESOLVED {{ rows.filter(row => row.resolved).length }}</span></div>
      <el-empty v-if="!rows.length" description="No issues recorded" />
      <article v-for="row in rows" :key="row.id" class="issue-row" :class="{ resolved: row.resolved }">
        <el-checkbox :model-value="row.resolved" @change="toggle(row)" />
        <div><div><el-tag size="small" effect="dark">{{ labels[row.issue_type] }}</el-tag><b>{{ row.topic || row.subject }}</b></div><p>{{ row.description }}</p><small v-if="row.solution">Resolution: {{ row.solution }}</small></div>
        <button class="text-danger" @click="drop(row)">Delete</button>
      </article>
    </section>
    <el-dialog v-model="open" title="Record issue" width="min(600px, 94vw)">
      <el-form label-position="top">
        <div class="form-pair">
          <el-form-item label="Subject"><el-select v-model="form.subject"><el-option v-for="(label, key) in subjects" :key="key" :label="label" :value="key" /></el-select></el-form-item>
          <el-form-item label="Type"><el-select v-model="form.issue_type"><el-option v-for="(label, key) in labels" :key="key" :label="label" :value="key" /></el-select></el-form-item>
        </div>
        <el-form-item label="Topic"><el-input v-model="form.topic" /></el-form-item>
        <el-form-item label="Description"><el-input v-model="form.description" type="textarea" :rows="4" /></el-form-item>
        <el-form-item label="Resolution"><el-input v-model="form.solution" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="open = false">Cancel</el-button><el-button type="primary" @click="create">Save issue</el-button></template>
    </el-dialog>
  </div>
</template>
