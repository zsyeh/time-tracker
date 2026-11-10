<script setup lang="ts">
import { uiText } from '../lib/uiText'
import { onMounted, ref } from 'vue'
import { api } from '../lib/api'
import type { Page } from '../types'
interface Erratum { id:number; question_uuid:string; question_label:string; document:string; reporter:string; kind_label:string; description:string; status:'open'|'reviewing'|'resolved'|'declined'; resolution:string; created_at:string }
const data=ref<Page<Erratum>|null>(null), loading=ref(true), error=ref(''), page=ref(1)
async function load(target=1){ loading.value=true; error.value=''; try{ data.value=await api<Page<Erratum>>(`/api/drill/errata/?page=${target}`); page.value=target }catch(reason){ error.value=(reason as Error).message }finally{ loading.value=false } }
onMounted(()=>void load())
</script>
<template><section class="page errata-page"><header class="page-header"><div><span class="eyebrow">{{ uiText("PUBLIC QUEUE") }}</span><h1>{{ uiText("Errata") }}</h1><p>{{ uiText("同一工作区的勘误公开可见；核对原始资料后更新处理状态。") }}</p></div></header><p v-if="error" class="error-state">{{ uiText(error) }}</p><div v-else-if="loading" class="question-skeleton">{{ uiText("LOADING ERRATA…") }}</div><div v-else-if="data" class="errata-list"><article v-for="item in data.results" :key="item.id"><header><RouterLink :to="`/practice/${item.question_uuid}`">{{ item.question_label }}</RouterLink><span :class="`erratum-status ${item.status}`">{{ item.status }}</span></header><small>{{ item.document }} · {{ item.kind_label }} · {{ item.reporter }} · {{ new Date(item.created_at).toLocaleString() }}</small><p>{{ item.description }}</p><blockquote v-if="item.resolution"><strong>{{ uiText("Resolution") }}</strong>{{ item.resolution }}</blockquote></article><p v-if="!data.results.length" class="empty-state">{{ uiText("No corrections have been submitted.") }}</p><nav v-if="data.previous || data.next" class="pagination"><button :disabled="!data.previous" @click="load(page-1)">{{ uiText("← Previous") }}</button><span>Page {{ page }}</span><button :disabled="!data.next" @click="load(page+1)">{{ uiText("Next →") }}</button></nav></div></section></template>
