<script setup lang="ts">
import { uiText } from '../lib/uiText'
import { useRoute } from 'vue-router'
import { buildListContext, previewLocation } from '../lib/listContext'
const route = useRoute()
import { onMounted, ref } from 'vue'
import { api } from '../lib/api'
import type { Page } from '../types'
interface Erratum { id:number; question_uuid:string; question_label:string; document:string; reporter:string; kind_label:string; description:string; status:'open'|'reviewing'|'resolved'|'declined'; resolution:string; created_at:string }
const data=ref<Page<Erratum>|null>(null), loading=ref(true), error=ref(''), page=ref(1)
async function load(target=1){ loading.value=true; error.value=''; try{ data.value=await api<Page<Erratum>>(`/api/drill/errata/?page=${target}`); page.value=target }catch(reason){ error.value=(reason as Error).message }finally{ loading.value=false } }
onMounted(()=>void load())
</script>
<template><section class="page errata-page"><header class="page-header"><div><h1>{{ uiText("Errata") }}</h1><p>{{ uiText("同一工作区的勘误公开可见；核对原始资料后更新处理状态。") }}</p></div><RouterLink :to="previewLocation(buildListContext('errata', route.query, route.fullPath))">{{ uiText("全局预览") }}</RouterLink></header><p v-if="error" class="error-state">{{ uiText(error) }}</p><div v-else-if="loading" class="question-skeleton">{{ uiText("LOADING ERRATA…") }}</div><div v-else-if="data" class="errata-list"><article v-for="item in data.results" :key="item.id"><header><RouterLink :to="`/practice/${item.question_uuid}`">{{ item.question_label }}</RouterLink><span :class="`erratum-status ${item.status}`">{{ item.status }}</span></header><small>{{ item.document }} · {{ item.kind_label }} · {{ item.reporter }} · {{ new Date(item.created_at).toLocaleString() }}</small><p>{{ item.description }}</p><blockquote v-if="item.resolution"><strong>{{ uiText("Resolution") }}</strong>{{ item.resolution }}</blockquote></article><p v-if="!data.results.length" class="empty-state">{{ uiText("No corrections have been submitted.") }}</p><nav v-if="data.previous || data.next" class="pagination"><button :disabled="!data.previous" @click="load(page-1)">{{ uiText("← Previous") }}</button><span>Page {{ page }}</span><button :disabled="!data.next" @click="load(page+1)">{{ uiText("Next →") }}</button></nav></div></section></template>


<style scoped>
.errata-list { border-top: 1px solid var(--border-subtle); }
.errata-list > article { padding: 15px 4px; border-bottom: 1px solid var(--border-subtle); }
.errata-list article > header { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.errata-list article > header a { color: var(--text-primary); font-size: 13px; font-weight: 600; }
.errata-list article > small { color: var(--text-tertiary); font-size: 12px; }
.errata-list article > p { margin-top: 9px; color: var(--text-secondary); white-space: pre-wrap; font-size: 12px; }
.errata-list blockquote { margin-top: 10px; padding: 9px 11px; border-left: 2px solid var(--success); color: var(--text-secondary); background: color-mix(in srgb, var(--success) 6%, transparent); font-size: 12px; }
.errata-list blockquote strong { margin-right: 8px; color: var(--success); }
.errata-list article > header { flex-wrap:wrap; } .errata-list article > p { font-size:14px; line-height:1.6; } .errata-list blockquote { border-left:0; border-radius:4px; background:var(--surface-subtle); font-size:13px; }
</style>
