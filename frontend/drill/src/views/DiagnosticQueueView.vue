<script setup lang="ts">
import { uiText } from '../lib/uiText'
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../lib/api'
import type { ReviewPlan } from '../types'

const route = useRoute(), router = useRouter()
const loading = ref(true), error = ref('')
const rows = ref<Array<{ uuid:string; label:string; document:string; topic:string; plan:ReviewPlan }>>([])

async function load(){loading.value=true;error.value='';try{const params=new URLSearchParams();if(route.query.error)params.set('error',String(route.query.error));if(route.query.queue)params.set('queue',String(route.query.queue));else params.set('queue','active');const payload=await api<{count:number;results:typeof rows.value}>(`/api/drill/diagnostics/questions/?${params}`);rows.value=payload.results}catch(reason){error.value=(reason as Error).message}finally{loading.value=false}}
function open(uuid:string){void router.push({path:`/practice/${uuid}`,query:{from:'diagnostics',mode:route.query.error?'method':''}})}
watch(()=>route.fullPath,()=>void load())
onMounted(()=>void load())
</script>

<template><section class="page queue-page"><header class="page-header"><div><span class="eyebrow">CLOSED-LOOP TRAINING</span><h1>{{ route.query.error ? uiText("知识知道但不会做") : uiText("待巩固队列") }}</h1><p>{{ uiText("默认隐藏答案；先确定知识点与第一步关系式，再完整解题。") }}</p></div></header><p v-if="error" class="error-state">{{error}}</p><div v-if="loading" class="question-skeleton">{{ uiText("加载闭环队列…") }}</div><div v-else class="queue-list"><button v-for="row in rows" :key="row.uuid" @click="open(row.uuid)"><span><strong>{{row.label}}</strong><small>{{row.document}} · {{row.topic}}</small></span><span><b>{{row.plan.checkpoint}}</b><small>{{row.plan.next_review_at?new Date(row.plan.next_review_at).toLocaleString():uiText("未安排")}}</small></span><i>→</i></button><p v-if="!rows.length">{{ uiText("当前没有符合条件的题目。") }}</p></div></section></template>

<style scoped>.page-header p{color:var(--text-tertiary);font-size:11px}.queue-list{display:grid;gap:7px}.queue-list button{display:grid;grid-template-columns:1fr auto 20px;align-items:center;gap:12px;padding:13px;border:1px solid var(--border-subtle);border-radius:9px;color:var(--text-primary);background:var(--bg-surface);text-align:left;cursor:pointer}.queue-list button>span{display:grid;gap:4px}.queue-list small{color:var(--text-tertiary);font-size:9px}.queue-list b{color:#e0b238}.queue-list i{font-style:normal}.queue-list>p{color:var(--text-tertiary)}</style>
