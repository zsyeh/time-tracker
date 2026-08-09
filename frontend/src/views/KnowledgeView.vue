<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api, patch, post, remove } from '../lib/api'
import type { KnowledgePoint } from '../types'
const rows=ref<KnowledgePoint[]>([]), open=ref(false), loading=ref(false)
const form=reactive({subject:'math',name:'',parent:null as number|null,importance:3,mastery_score:0,status:'unknown'})
const grouped=computed(()=>Object.entries(rows.value.reduce((acc,row)=>{(acc[row.subject] ||= []).push(row);return acc},{} as Record<string,KnowledgePoint[]>)))
const subjectLabels:Record<string,string>={math:'数学',english:'英语',major:'专业课',training:'训练'}
async function load(){loading.value=true;try{rows.value=await api<KnowledgePoint[]>('/api/knowledge/')}catch(e){ElMessage.error((e as Error).message)}finally{loading.value=false}}
async function create(){try{await post('/api/knowledge/',form);open.value=false;form.name='';await load()}catch(e){ElMessage.error((e as Error).message)}}
async function update(row:KnowledgePoint,value:number){await patch(`/api/knowledge/${row.id}/`,{mastery_score:value,status:value>=90?'automatic':value>=70?'stable':value>=40?'understood':'learning'});await load()}
async function drop(row:KnowledgePoint){await remove(`/api/knowledge/${row.id}/`);await load()}
onMounted(load)
</script>
<template><div class="view-stack"><section class="page-intro action-intro"><div><span class="eyebrow">KNOWLEDGE MAP</span><h1>知识结构</h1><p>按科目建立知识点，并持续校准掌握程度。</p></div><el-button type="primary" @click="open=true">添加知识点</el-button></section><section v-loading="loading" class="knowledge-grid"><article v-for="group in grouped" :key="group[0]" class="panel knowledge-group"><h2>{{ subjectLabels[group[0]] }}</h2><div v-for="row in group[1]" :key="row.id" class="knowledge-row"><div><strong>{{ row.name }}</strong><small>重要度 {{ row.importance }} · 复习 {{ row.review_count }} 次</small></div><el-progress :percentage="row.mastery_score" :stroke-width="8" :color="row.mastery_score>=70?'#dfff72':'#2d8c70'"/><el-slider :model-value="row.mastery_score" :show-tooltip="false" @change="(v:number)=>update(row,v)"/><button class="text-danger" @click="drop(row)">删除</button></div></article><el-empty v-if="!rows.length" class="panel" description="还没有知识点" /></section><el-dialog v-model="open" title="添加知识点" width="min(520px,94vw)"><el-form label-position="top"><el-form-item label="科目"><el-select v-model="form.subject"><el-option v-for="(label,key) in subjectLabels" :key="key" :label="label" :value="key"/></el-select></el-form-item><el-form-item label="知识点名称"><el-input v-model="form.name"/></el-form-item><el-form-item label="重要度"><el-rate v-model="form.importance"/></el-form-item><el-form-item label="初始掌握度"><el-slider v-model="form.mastery_score"/></el-form-item></el-form><template #footer><el-button @click="open=false">取消</el-button><el-button type="primary" @click="create">添加</el-button></template></el-dialog></div></template>
