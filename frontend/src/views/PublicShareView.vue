<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { publicApi } from '../lib/api'
import type { PublicSharedSession } from '../types'
import MarkdownPreview from '../components/MarkdownPreview.vue'

const props = defineProps<{ token: string }>()
const article = ref<PublicSharedSession | null>(null)
const loading = ref(true)
const unavailable = ref(false)
const subjects = { math: 'Mathematics', english: 'English', major: 'Major', training: 'Training' }

function duration(minutes: number) {
  return minutes >= 60 ? `${Math.floor(minutes / 60)}h ${minutes % 60}m` : `${minutes}m`
}

async function load() {
  loading.value = true
  unavailable.value = false
  article.value = null
  try {
    article.value = await publicApi<PublicSharedSession>(`/api/public/shares/${encodeURIComponent(props.token)}/`)
    document.title = `${article.value.title} · Learning OS`
  } catch {
    unavailable.value = true
    document.title = 'Shared article unavailable · Learning OS'
  } finally { loading.value = false }
}

watch(() => props.token, load)
onMounted(load)
</script>

<template>
  <main class="public-share-page" v-loading="loading">
    <header class="public-share-header"><a href="/today" class="brand"><span class="brand-mark">L</span><div><strong>Learning OS</strong><small>SHARED ARTICLE</small></div></a><span>READ ONLY</span></header>
    <section v-if="unavailable" class="panel public-share-unavailable"><span class="eyebrow">SHARE / UNAVAILABLE</span><h1>This article is unavailable</h1><p>The link is invalid, expired, or has been revoked.</p></section>
    <article v-else-if="article" class="panel public-article">
      <header><span class="eyebrow">PUBLIC SESSION ARTICLE</span><h1>{{ article.title }}</h1><div class="public-article-meta"><span>{{ subjects[article.subject] }}</span><time>{{ new Date(article.start_time).toLocaleString('en-GB') }}</time><span>{{ duration(article.duration_minutes) }}</span></div></header>
      <MarkdownPreview :source="article.markdown" default-open allow-fullscreen empty-text="No article content was shared." />
    </article>
    <footer class="public-share-footer">SANITIZED MARKDOWN · NO ACCOUNT DATA · READ ONLY</footer>
  </main>
</template>
