<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../lib/api'
import type { CollectionPayload } from '../types'

const props = defineProps<{ kind: 'favorite' | 'review_later' }>()
const router = useRouter()
const data = ref<CollectionPayload | null>(null)
const loading = ref(true)
const error = ref('')
const page = ref(1)

const copy = () => props.kind === 'favorite'
  ? { eyebrow: 'SAVED COLLECTION', title: 'Favorites', description: 'Questions you starred for quick access.' }
  : { eyebrow: 'NEXT PRACTICE QUEUE', title: 'Next Time', description: 'Questions you set aside to revisit.' }

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await api<CollectionPayload>(`/api/drill/collections/?kind=${props.kind}&page=${page.value}`)
  } catch (reason) {
    error.value = (reason as Error).message
  } finally {
    loading.value = false
  }
}

function openQuestion(uuid: string) {
  void router.push({ path: `/practice/${uuid}`, query: { from: 'collection', collection: props.kind } })
}

watch(() => props.kind, () => { page.value = 1; void load() })
onMounted(load)
</script>

<template>
  <section class="page collection-page">
    <header class="page-header">
      <div><span class="eyebrow">{{ copy().eyebrow }}</span><h1>{{ copy().title }}</h1><p>{{ copy().description }}</p></div>
      <strong class="collection-count">{{ data?.count || 0 }}</strong>
    </header>
    <p v-if="error" class="error-state">{{ error }}</p>
    <div v-else-if="loading" class="question-skeleton">LOADING SAVED QUESTIONS…</div>
    <div v-else class="question-list">
      <button v-for="question in data?.results" :key="question.uuid" class="question-row" @click="openQuestion(question.uuid)">
        <span class="question-index">{{ props.kind === 'favorite' ? '★' : '↻' }}</span>
        <span class="question-copy"><strong>{{ question.display_label || `Question ${question.question_order}` }}</strong><small>{{ question.document }} · {{ question.topic || 'General' }}</small><em v-if="question.saved_note">{{ question.saved_note }}</em></span>
        <span class="attempt-mark" :class="`status-${question.state}`">{{ question.attempt_count || '' }}</span>
        <b class="row-arrow">→</b>
      </button>
      <div v-if="!data?.results.length" class="empty-state">{{ props.kind === 'favorite' ? 'No favorites yet. Star a question from Practice.' : 'Nothing is queued for next time.' }}</div>
    </div>
    <footer v-if="data && (data.previous || data.next)" class="pager"><button :disabled="!data.previous" @click="page--; load()">← Previous</button><span>PAGE {{ page }}</span><button :disabled="!data.next" @click="page++; load()">Next →</button></footer>
  </section>
</template>
