<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api, patch, post, remove } from '../lib/api'
import type { KnowledgePoint } from '../types'

const rows = ref<KnowledgePoint[]>([])
const open = ref(false)
const loading = ref(false)
const form = reactive({ subject: 'math', name: '', parent: null as number | null, importance: 3, mastery_score: 0, status: 'unknown' })
const grouped = computed(() => Object.entries(rows.value.reduce((acc, row) => { (acc[row.subject] ||= []).push(row); return acc }, {} as Record<string, KnowledgePoint[]>)))
const subjectLabels: Record<string, string> = { math: 'Mathematics', english: 'English', major: 'Major', training: 'Training' }

async function load() {
  loading.value = true
  try { rows.value = await api<KnowledgePoint[]>('/api/knowledge/') }
  catch (error) { ElMessage.error((error as Error).message) }
  finally { loading.value = false }
}
async function create() {
  try { await post('/api/knowledge/', form); open.value = false; form.name = ''; await load() }
  catch (error) { ElMessage.error((error as Error).message) }
}
async function update(row: KnowledgePoint, value: number) {
  await patch(`/api/knowledge/${row.id}/`, { mastery_score: value, status: value >= 90 ? 'automatic' : value >= 70 ? 'stable' : value >= 40 ? 'understood' : 'learning' })
  await load()
}
async function drop(row: KnowledgePoint) { await remove(`/api/knowledge/${row.id}/`); await load() }
onMounted(load)
</script>

<template>
  <div class="view-stack">
    <section class="page-intro action-intro"><div><span class="eyebrow">KNOWLEDGE INVENTORY</span><h1>Knowledge</h1><p>Subject-level mastery values and review counts.</p></div><el-button type="primary" @click="open = true">New point</el-button></section>
    <section v-loading="loading" class="knowledge-grid">
      <article v-for="group in grouped" :key="group[0]" class="panel knowledge-group">
        <h2>{{ subjectLabels[group[0]] }}</h2>
        <div v-for="row in group[1]" :key="row.id" class="knowledge-row">
          <div><strong>{{ row.name }}</strong><small>IMPORTANCE {{ row.importance }} · {{ row.review_count }} REVIEWS</small></div>
          <el-progress :percentage="row.mastery_score" :stroke-width="8" :color="row.mastery_score >= 70 ? '#f0a7ff' : '#6f59d9'" />
          <el-slider :model-value="row.mastery_score" :show-tooltip="false" @change="(value: number) => update(row, value)" />
          <button class="text-danger" @click="drop(row)">Delete</button>
        </div>
      </article>
      <el-empty v-if="!rows.length" class="panel" description="No knowledge points" />
    </section>
    <el-dialog v-model="open" title="Add knowledge point" width="min(520px, 94vw)">
      <el-form label-position="top">
        <el-form-item label="Subject"><el-select v-model="form.subject"><el-option v-for="(label, key) in subjectLabels" :key="key" :label="label" :value="key" /></el-select></el-form-item>
        <el-form-item label="Name"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="Importance"><el-rate v-model="form.importance" /></el-form-item>
        <el-form-item label="Initial mastery"><el-slider v-model="form.mastery_score" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="open = false">Cancel</el-button><el-button type="primary" @click="create">Add point</el-button></template>
    </el-dialog>
  </div>
</template>
