<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api, post } from './lib/api'
import { configureWorkspaceScope } from './lib/workspace'
import type { Progress } from './types'

const route = useRoute()
const username = ref('')
const progress = ref<Progress | null>(null)
const sidebarOpen = ref(false)
const landscape = ref(false)
const identityReady = ref(false)

async function loadIdentity() {
  const auth = await api<{ user: { username: string } }>('/api/auth/session/')
  configureWorkspaceScope(auth.user.username)
  username.value = auth.user.username
  identityReady.value = true
  progress.value = await api<Progress>('/api/drill/progress/')
}

async function logout() {
  await post('/api/auth/logout/', {})
  location.assign('/accounts/login/')
}

watch(() => route.fullPath, () => {
  if (landscape.value) sidebarOpen.value = false
})

onMounted(() => {
  landscape.value = window.matchMedia('(orientation: landscape)').matches
  void loadIdentity()
})
</script>

<template>
  <div class="drill-shell" :class="{ 'drawer-open': sidebarOpen }">
    <button class="drawer-toggle" type="button" aria-label="Open navigation" @click="sidebarOpen = true"><span /><span /><span /></button>
    <button v-if="sidebarOpen" class="drawer-backdrop" type="button" aria-label="Close navigation" @click="sidebarOpen = false" />
    <aside class="drill-sidebar">
      <button class="drawer-close" type="button" aria-label="Close navigation" @click="sidebarOpen = false">×</button>
      <RouterLink class="wordmark" to="/practice" aria-label="Drill home">
        <span>D</span><strong>DRILL</strong><small>QUESTION PRACTICE</small>
      </RouterLink>
      <nav>
        <RouterLink to="/practice" :class="{ active: route.name === 'practice' || route.name === 'question' }">
          <i>01</i><span>Practice</span>
        </RouterLink>
        <RouterLink to="/heatmap" :class="{ active: route.name === 'heatmap' }">
          <i>02</i><span>Heatmaps</span>
        </RouterLink>
        <RouterLink to="/paper" :class="{ active: route.name === 'paper' }">
          <i>03</i><span>Build Paper</span>
        </RouterLink>
        <RouterLink to="/favorites" :class="{ active: route.name === 'favorites' }">
          <i>04</i><span>Favorites</span>
        </RouterLink>
        <RouterLink to="/review-later" :class="{ active: route.name === 'review-later' }">
          <i>05</i><span>Next Time</span>
        </RouterLink>
        <RouterLink to="/feel" :class="{ active: route.name === 'feel' }">
          <i>06</i><span>Book Feel</span>
        </RouterLink>
        <RouterLink to="/insight" :class="{ active: route.name === 'insight' }">
          <i>07</i><span>Insight</span>
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
    <main><RouterView v-if="identityReady" /></main>
  </div>
</template>
