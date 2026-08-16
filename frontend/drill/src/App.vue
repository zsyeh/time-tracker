<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api, post } from './lib/api'
import type { Progress } from './types'

const route = useRoute()
const username = ref('')
const progress = ref<Progress | null>(null)

async function loadIdentity() {
  const [auth, data] = await Promise.all([
    api<{ user: { username: string } }>('/api/auth/session/'),
    api<Progress>('/api/drill/progress/'),
  ])
  username.value = auth.user.username
  progress.value = data
}

async function logout() {
  await post('/api/auth/logout/', {})
  location.assign('/accounts/login/')
}

onMounted(() => void loadIdentity())
</script>

<template>
  <div class="drill-shell">
    <aside class="drill-sidebar">
      <RouterLink class="wordmark" to="/practice" aria-label="Drill home">
        <span>D</span><strong>DRILL</strong><small>QUESTION PRACTICE</small>
      </RouterLink>
      <nav>
        <RouterLink to="/practice" :class="{ active: route.name === 'practice' || route.name === 'question' }">
          <i>01</i><span>Practice</span>
        </RouterLink>
        <RouterLink to="/heatmap" :class="{ active: route.name === 'heatmap' }">
          <i>02</i><span>Past Papers</span>
        </RouterLink>
      </nav>
      <div v-if="progress" class="sidebar-progress">
        <span>YOUR COVERAGE</span>
        <strong>{{ progress.attempted_questions }}<small>/ {{ progress.question_count }}</small></strong>
        <div><i :style="{ width: `${Math.min(100, progress.attempted_questions / Math.max(1, progress.question_count) * 100)}%` }" /></div>
        <p>{{ progress.total_attempts }} attempts</p>
      </div>
      <p class="sidebar-credit"><span>QUESTION SOURCES</span>Thanks to Bilibili creator <strong>cxy</strong> for collecting and organizing the question bank.</p>
      <div class="account">
        <span>{{ username.slice(0, 1).toUpperCase() }}</span>
        <div><strong>{{ username }}</strong><button @click="logout">Sign out</button></div>
      </div>
    </aside>
    <main><RouterView /></main>
  </div>
</template>
