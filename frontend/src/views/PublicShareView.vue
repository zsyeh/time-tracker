<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { publicApi } from '../lib/api'
import type { PublicSharedSession } from '../types'
import MarkdownPreview from '../components/MarkdownPreview.vue'

const props = defineProps<{ token: string }>()
const article = ref<PublicSharedSession | null>(null)
const loading = ref(true)
const unavailable = ref(false)
const subjects = { math: 'Mathematics', english: 'English', major: 'Major', training: 'Politics' }

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


<style scoped>
.public-share-page { width: min(920px, calc(100% - 32px)); min-height: 100vh; margin: 0 auto; padding: 20px 0 32px; }
.public-share-header { height: 48px; margin-bottom: 16px; display: flex; align-items: center; justify-content: space-between; }
.public-share-header .brand { color: var(--text-primary); text-decoration: none; }
.public-share-header > span { color: var(--text-tertiary); font-size: 12px; }
.public-article { padding: clamp(22px, 4vw, 48px); }
.public-article > header { margin-bottom: 22px; padding-bottom: 16px; border-bottom: 1px solid var(--border-subtle); }
.public-article h1 { max-width: 760px; margin: 5px 0 12px; font-size: clamp(27px, 4.2vw, 42px); line-height: 1.12; letter-spacing: -.04em; overflow-wrap: anywhere; }
.public-article-meta { color: var(--text-tertiary); display: flex; flex-wrap: wrap; gap: 8px 14px; font-size: 12px; }
.public-share-unavailable { max-width: 640px; margin: 14vh auto; padding: 32px; }
.public-share-footer { padding: 18px 0; color: var(--text-tertiary); text-align: center; font-size: 12px; }
.public-share-page { min-width:0; padding-top:max(16px,env(safe-area-inset-top)); padding-bottom:max(24px,env(safe-area-inset-bottom)); } .public-article,.public-share-unavailable { border:0; border-radius:0; background:transparent; box-shadow:none; } .public-article { padding:24px 0; } .public-share-unavailable { margin:12vh auto; }
</style>
