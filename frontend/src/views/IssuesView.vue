<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Filter, Operation, Search, View } from '@element-plus/icons-vue'
import { api, patch, post, remove } from '../lib/api'
import type { Issue, Page } from '../types'
import MarkdownPreview from '../components/MarkdownPreview.vue'
import PageHeader from '../components/layout/PageHeader.vue'
import PageToolbar from '../components/layout/PageToolbar.vue'
import MenuPopover from '../components/ui/MenuPopover.vue'
import ToolbarChip from '../components/ui/ToolbarChip.vue'

const rows = ref<Issue[]>([])
const open = ref(false)
const loading = ref(false)
const query = ref('')
const statusFilter = ref<'active' | 'resolved' | 'all'>('active')
const subjectFilter = ref('')
const typeFilter = ref('')
const groupBy = ref<'status' | 'subject' | 'type' | 'none'>('status')
const density = ref<'compact' | 'comfortable'>('compact')
const properties = reactive({ type: true, subject: true, date: true, repeats: true, description: true })
const form = reactive({ subject: 'math', topic: '', issue_type: 'concept_error', description: '', solution: '', repeat_count: 1 })
const labels: Record<string, string> = {
  concept_error: 'Concept error', calculation_error: 'Calculation error', recognition_error: 'Recognition error',
  memory_error: 'Memory error', speed_problem: 'Speed problem', careless_error: 'Careless error', strategy_problem: 'Strategy problem',
}
const subjects = { math: 'Mathematics', english: 'English', major: 'Major', training: 'Training' }
const activeCount = computed(() => rows.value.filter((row) => !row.resolved).length)
const resolvedCount = computed(() => rows.value.filter((row) => row.resolved).length)
const filteredRows = computed(() => rows.value.filter((row) => {
  if (statusFilter.value === 'active' && row.resolved) return false
  if (statusFilter.value === 'resolved' && !row.resolved) return false
  if (subjectFilter.value && row.subject !== subjectFilter.value) return false
  if (typeFilter.value && row.issue_type !== typeFilter.value) return false
  const needle = query.value.trim().toLowerCase()
  return !needle || [row.topic, row.description, row.solution, labels[row.issue_type], subjects[row.subject]].some((value) => String(value || '').toLowerCase().includes(needle))
}))
const issueGroups = computed(() => {
  const groups = new Map<string, Issue[]>()
  for (const row of filteredRows.value) {
    const key = groupBy.value === 'status' ? (row.resolved ? 'Resolved' : 'Active')
      : groupBy.value === 'subject' ? subjects[row.subject]
        : groupBy.value === 'type' ? labels[row.issue_type]
          : 'Issues'
    groups.set(key, [...(groups.get(key) || []), row])
  }
  return [...groups.entries()].map(([label, issues]) => ({ label, issues }))
})

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
  <div class="workspace-view issues-view">
    <PageHeader context="Workspace" title="Issues" :metadata="`${activeCount} active · ${resolvedCount} resolved`"><template #actions><el-button type="primary" @click="open = true">New issue</el-button></template></PageHeader>
    <PageToolbar label="Issue filters and display">
      <ToolbarChip label="Active" :count="activeCount" :active="statusFilter === 'active'" :pressed="statusFilter === 'active'" @click="statusFilter = 'active'" />
      <ToolbarChip label="Resolved" :count="resolvedCount" :active="statusFilter === 'resolved'" :pressed="statusFilter === 'resolved'" @click="statusFilter = 'resolved'" />
      <ToolbarChip label="All" :count="rows.length" :active="statusFilter === 'all'" :pressed="statusFilter === 'all'" @click="statusFilter = 'all'" />
      <template #actions>
        <label class="toolbar-search"><el-icon><Search /></el-icon><input v-model="query" type="search" placeholder="Search issues" aria-label="Search issues" /></label>
        <MenuPopover label="Filter" align="end">
          <template #trigger><el-icon><Filter /></el-icon><span>Filter</span><b v-if="subjectFilter || typeFilter" class="control-count">{{ Number(Boolean(subjectFilter)) + Number(Boolean(typeFilter)) }}</b></template>
          <div class="menu-section"><span>Subject</span><button type="button" class="menu-option" :class="{ selected: !subjectFilter }" @click="subjectFilter = ''"><i />All subjects<small>⌘A</small></button><button v-for="(label, key) in subjects" :key="key" type="button" class="menu-option" :class="{ selected: subjectFilter === key }" @click="subjectFilter = key"><i />{{ label }}</button></div>
          <div class="menu-section"><span>Issue type</span><button type="button" class="menu-option" :class="{ selected: !typeFilter }" @click="typeFilter = ''"><i />All types</button><button v-for="(label, key) in labels" :key="key" type="button" class="menu-option" :class="{ selected: typeFilter === key }" @click="typeFilter = key"><i />{{ label }}</button></div>
        </MenuPopover>
        <MenuPopover label="Properties" align="end">
          <template #trigger><el-icon><View /></el-icon><span>Display</span></template>
          <div class="menu-section"><span>Visible properties</span><label v-for="(_, key) in properties" :key="key" class="menu-toggle"><span>{{ key === 'repeats' ? 'Repeat count' : key }}</span><el-switch v-model="properties[key]" size="small" /></label></div>
        </MenuPopover>
        <MenuPopover label="View options" align="end">
          <template #trigger><el-icon><Operation /></el-icon><span>View</span></template>
          <div class="menu-section"><span>Group by</span><button v-for="option in (['status', 'subject', 'type', 'none'] as const)" :key="option" type="button" class="menu-option" :class="{ selected: groupBy === option }" @click="groupBy = option"><i />{{ option }}</button></div>
          <div class="menu-section"><span>Density</span><button v-for="option in (['compact', 'comfortable'] as const)" :key="option" type="button" class="menu-option" :class="{ selected: density === option }" @click="density = option"><i />{{ option }}</button></div>
        </MenuPopover>
      </template>
    </PageToolbar>
    <section class="issue-board" :class="`density-${density}`" v-loading="loading">
      <el-empty v-if="!filteredRows.length && !loading" description="No issues match this view" />
      <section v-for="group in issueGroups" :key="group.label" class="resource-group">
        <header class="resource-group-header"><div><span class="group-disclosure">⌄</span><strong>{{ group.label }}</strong><b>{{ group.issues.length }}</b></div><span>{{ groupBy === 'none' ? 'Current view' : `Grouped by ${groupBy}` }}</span></header>
        <article v-for="row in group.issues" :key="row.id" class="issue-row" :class="{ resolved: row.resolved }">
          <el-checkbox :model-value="row.resolved" :aria-label="row.resolved ? 'Reopen issue' : 'Resolve issue'" @change="toggle(row)" />
          <span class="resource-key">ISS-{{ row.id }}</span>
          <div class="issue-main"><div><b>{{ row.topic || subjects[row.subject] }}</b><span v-if="properties.type" class="row-property">{{ labels[row.issue_type] }}</span></div><p v-if="properties.description">{{ row.description || 'No description' }}</p><small v-if="row.solution">Resolution · {{ row.solution }}</small></div>
          <div class="issue-properties"><span v-if="properties.subject">{{ subjects[row.subject] }}</span><span v-if="properties.repeats && row.repeat_count > 1">×{{ row.repeat_count }}</span><time v-if="properties.date">{{ new Date(row.created_at).toLocaleDateString('en-CA', { month: 'short', day: 'numeric' }) }}</time></div>
          <button class="row-action-danger" aria-label="Delete issue" @click="drop(row)">Delete</button>
        </article>
      </section>
    </section>
    <el-dialog v-model="open" title="Record issue" width="min(600px, 94vw)" destroy-on-close>
      <el-form label-position="top">
        <div class="form-pair">
          <el-form-item label="Subject"><el-select v-model="form.subject"><el-option v-for="(label, key) in subjects" :key="key" :label="label" :value="key" /></el-select></el-form-item>
          <el-form-item label="Type"><el-select v-model="form.issue_type"><el-option v-for="(label, key) in labels" :key="key" :label="label" :value="key" /></el-select></el-form-item>
        </div>
        <el-form-item label="Topic"><el-input v-model="form.topic" /></el-form-item>
        <el-form-item label="Description"><el-input v-model="form.description" type="textarea" :rows="4" placeholder="Plain text or Markdown" /></el-form-item>
        <MarkdownPreview :source="form.description" />
        <el-form-item label="Resolution"><el-input v-model="form.solution" type="textarea" :rows="3" placeholder="Plain text or Markdown" /></el-form-item>
        <MarkdownPreview :source="form.solution" />
      </el-form>
      <template #footer><el-button @click="open = false">Cancel</el-button><el-button type="primary" @click="create">Save issue</el-button></template>
    </el-dialog>
  </div>
</template>
