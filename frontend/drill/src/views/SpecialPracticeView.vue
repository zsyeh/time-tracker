<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../lib/api'
import { buildListContext, previewLocation, previewQuestionLocation } from '../lib/listContext'
type Training = {uuid:string;title:string;description:string;created_at:string;question_count:number;first_question:string|null;first_item:number|null}
const tasks=ref<Training[]>([]),loading=ref(true),error=ref('')
function context(task:Training){return buildListContext('paper',{paper:task.uuid},'/special-practice')}
function start(task:Training){return previewQuestionLocation(context(task),{entry_id:`paper:${task.first_item}`,question_uuid:task.first_question!,index:0})}
async function load(){loading.value=true;error.value='';try{tasks.value=(await api<{results:Training[]}>('/api/drill/special-practice/')).results}catch(e){error.value=(e as Error).message}finally{loading.value=false}}
onMounted(load)
</script>
<template><section class="page special-practice"><header><h1>专练模式</h1><p>Agent 推送的专项题单 · 使用标准 Practice 练习</p></header><p v-if="loading" role="status">加载题单…</p><p v-else-if="error" role="alert">{{ error }} <button @click="load">重试</button></p><p v-else-if="!tasks.length" class="empty-state">暂无专练题单。告诉 Agent 训练目标和选题要求，推送后会在这里显示。</p><ol v-else class="training-list"><li v-for="task in tasks" :key="task.uuid"><div><h2>{{ task.title }}</h2><p v-if="task.description" class="description">{{ task.description }}</p><small>{{ task.question_count }} 道题 · {{ new Date(task.created_at).toLocaleDateString() }}</small></div><nav :aria-label="task.title"><RouterLink v-if="task.first_question" :to="start(task)">开始专练</RouterLink><RouterLink :to="previewLocation(context(task))">全局预览</RouterLink></nav></li></ol></section></template>
<style scoped>
.special-practice{min-width:0}h1{font-size:24px;margin:0 0 8px}header p,.description,small{color:var(--text-secondary)}header{margin-bottom:24px}h2{font-size:17px;margin:0 0 8px}.training-list{list-style:none;margin:0;padding:0}.training-list li{display:flex;justify-content:space-between;align-items:center;gap:24px;padding:20px 0;border-bottom:1px solid var(--border-subtle)}.training-list li>div{min-width:0;overflow-wrap:anywhere}.description{font-size:14px;line-height:1.6;white-space:pre-wrap;margin:0 0 8px}small{font-size:13px}nav{display:flex;gap:16px;flex-shrink:0;flex-wrap:wrap}nav a{display:inline-flex;align-items:center;min-height:44px;color:var(--text-primary);text-decoration:none}nav a:hover{text-decoration:underline}@media(max-width:600px){.training-list li{align-items:flex-start;flex-direction:column;gap:8px}}
</style>
