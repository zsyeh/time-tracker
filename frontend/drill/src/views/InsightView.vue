<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../lib/api'
import type { InsightPayload } from '../types'

const router = useRouter()
const data = ref<InsightPayload | null>(null)
const loading = ref(true)
const error = ref('')

function openQuestion(uuid: string) {
  void router.push({ path: `/practice/${uuid}`, query: { from: 'insight' } })
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
}

onMounted(async () => {
  try {
    data.value = await api<InsightPayload>('/api/drill/insight/')
  } catch (reason) {
    error.value = (reason as Error).message
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <section class="page insight-page">
    <header class="page-header"><div><span class="eyebrow">YOUR ACTIVITY</span><h1>Insight</h1><p>Recent questions and notes, without turning practice into a dashboard.</p></div></header>
    <p v-if="error" class="error-state">{{ error }}</p>
    <div v-else-if="loading" class="question-skeleton">LOADING INSIGHT…</div>
    <div v-else class="insight-grid">
      <section><header><span>RECENT QUESTIONS</span><strong>{{ data?.recent_questions.length || 0 }}</strong></header><div class="insight-list"><button v-for="item in data?.recent_questions" :key="`${item.uuid}-${item.created_at}`" @click="openQuestion(item.uuid)"><span><strong>{{ item.label }}</strong><small>{{ item.document }} · {{ item.topic }}</small></span><span><em :class="`text-${item.result === 'review' ? 'review' : 'mastered'}`">{{ item.result }}</em><time>{{ formatTime(item.created_at) }}</time></span></button><p v-if="!data?.recent_questions.length">No recent practice yet.</p></div></section>
      <section><header><span>RECENT NOTES</span><strong>{{ data?.recent_notes.length || 0 }}</strong></header><div class="insight-list note-list"><button v-for="item in data?.recent_notes" :key="item.uuid" @click="openQuestion(item.uuid)"><span><strong>{{ item.label }}</strong><small>{{ item.document }} · {{ item.topic }}</small><p>{{ item.note }}</p></span><time>{{ formatTime(item.updated_at) }}</time></button><p v-if="!data?.recent_notes.length">No saved notes yet.</p></div></section>
    </div>
  </section>
</template>
