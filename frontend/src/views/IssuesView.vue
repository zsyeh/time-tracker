<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api, patch, post, remove } from '../lib/api'
import type { Issue, Page } from '../types'

const rows = ref<Issue[]>([]), open = ref(false), loading = ref(false)
const form = reactive({ subject: 'math', topic: '', issue_type: 'concept_error', description: '', solution: '', repeat_count: 1 })
const labels: Record<string,string> = { concept_error:'概念错误', calculation_error:'计算错误', recognition_error:'识别错误', memory_error:'记忆错误', speed_problem:'速度问题', careless_error:'粗心错误', strategy_problem:'策略问题' }
async function load() { loading.value = true; try { rows.value = (await api<Page<Issue>>('/api/issues/')).results } catch(e) { ElMessage.error((e as Error).message) } finally { loading.value = false } }
async function create() { try { await post('/api/issues/', form); open.value = false; Object.assign(form, { topic:'', description:'', solution:'', repeat_count:1 }); await load(); ElMessage.success('问题已记录') } catch(e) { ElMessage.error((e as Error).message) } }
async function toggle(row: Issue) { await patch(`/api/issues/${row.id}/`, { resolved: !row.resolved }); await load() }
async function drop(row: Issue) { await remove(`/api/issues/${row.id}/`); await load() }
onMounted(load)
</script>

<template><div class="view-stack"><section class="page-intro action-intro"><div><span class="eyebrow">ISSUE LOOP</span><h1>问题管理</h1><p>把错误变成可追踪、可关闭的学习反馈环。</p></div><el-button type="primary" @click="open=true">记录问题</el-button></section><section class="panel issue-board" v-loading="loading"><div class="board-heading"><span>待解决 {{ rows.filter(r=>!r.resolved).length }}</span><span>已解决 {{ rows.filter(r=>r.resolved).length }}</span></div><el-empty v-if="!rows.length" description="还没有学习问题" /><article v-for="row in rows" :key="row.id" class="issue-row" :class="{ resolved: row.resolved }"><el-checkbox :model-value="row.resolved" @change="toggle(row)" /><div><div><el-tag size="small" effect="dark">{{ labels[row.issue_type] }}</el-tag><b>{{ row.topic || row.subject }}</b></div><p>{{ row.description }}</p><small v-if="row.solution">解决办法：{{ row.solution }}</small></div><button class="text-danger" @click="drop(row)">删除</button></article></section><el-dialog v-model="open" title="记录学习问题" width="min(600px,94vw)"><el-form label-position="top"><div class="form-pair"><el-form-item label="科目"><el-select v-model="form.subject"><el-option label="数学" value="math"/><el-option label="英语" value="english"/><el-option label="专业课" value="major"/><el-option label="训练" value="training"/></el-select></el-form-item><el-form-item label="类型"><el-select v-model="form.issue_type"><el-option v-for="(label,key) in labels" :key="key" :label="label" :value="key"/></el-select></el-form-item></div><el-form-item label="主题"><el-input v-model="form.topic"/></el-form-item><el-form-item label="问题描述"><el-input v-model="form.description" type="textarea" :rows="4"/></el-form-item><el-form-item label="解决办法"><el-input v-model="form.solution" type="textarea" :rows="3"/></el-form-item></el-form><template #footer><el-button @click="open=false">取消</el-button><el-button type="primary" @click="create">保存</el-button></template></el-dialog></div></template>
