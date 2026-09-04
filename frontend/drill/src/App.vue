<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api, post } from './lib/api'
import { configureWorkspaceScope } from './lib/workspace'
import type { Progress } from './types'
import { useUiPreferences, type UiLanguage } from './lib/uiPreferences'

const route = useRoute()
const username = ref('')
const progress = ref<Progress | null>(null)
const sidebarOpen = ref(false)
const identityReady = ref(false)
const isEi = location.hostname.toLowerCase().startsWith('ei.')
const workspaceIcon = '/static/drill/drill-icon-180.png?v=img9392'
const { language, scheme, setLanguage, setScheme, t } = useUiPreferences()

document.title = isEi ? 'EI · 892 Practice' : 'Drill · Question Practice'

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
  sidebarOpen.value = false
})

onMounted(() => {
  void loadIdentity()
})
</script>

<template>
  <div class="drill-shell" :class="{ 'drawer-open': sidebarOpen, 'ei-workspace': isEi }">
    <button class="drawer-toggle" type="button" aria-label="Open navigation" aria-controls="drill-navigation" :aria-expanded="sidebarOpen" @click="sidebarOpen = true"><span /><span /><span /></button>
    <button v-if="sidebarOpen" class="drawer-backdrop" type="button" aria-label="Close navigation" @click="sidebarOpen = false" />
    <aside id="drill-navigation" class="drill-sidebar">
      <button class="drawer-close" type="button" aria-label="Close navigation" @click="sidebarOpen = false">×</button>
      <RouterLink class="wordmark" to="/practice" aria-label="Drill home">
        <img :src="workspaceIcon" alt="" aria-hidden="true" /><strong>{{ isEi ? '892 LAB' : 'DRILL' }}</strong><small>{{ isEi ? 'ELECTRONIC INFORMATION' : 'QUESTION PRACTICE' }}</small>
      </RouterLink>
      <nav>
        <RouterLink to="/practice" :class="{ active: route.name === 'practice' || route.name === 'question' }">
          <span>{{ t('practice') }}</span>
        </RouterLink>
        <RouterLink to="/activity" :class="{ active: route.name === 'activity' }">
          <span>{{ t('activity') }}</span>
        </RouterLink>
        <RouterLink to="/book-activity" :class="{ active: route.name === 'book-activity' }">
          <span>{{ t('bookActivity') }}</span>
        </RouterLink>
        <RouterLink to="/heatmap" :class="{ active: route.name === 'heatmap' }">
          <span>{{ t('knowledge') }}</span>
        </RouterLink>
        <RouterLink to="/paper" :class="{ active: route.name === 'paper' }">
          <span>{{ t('buildPaper') }}</span>
        </RouterLink>
        <RouterLink to="/favorites" :class="{ active: route.name === 'favorites' }">
          <span>{{ t('favorites') }}</span>
        </RouterLink>
        <RouterLink to="/review-later" :class="{ active: route.name === 'review-later' }">
          <span>{{ t('nextTime') }}</span>
        </RouterLink>
        <RouterLink to="/feel" :class="{ active: route.name === 'feel' }">
          <span>{{ t('bookFeel') }}</span>
        </RouterLink>
        <RouterLink to="/insight" :class="{ active: route.name === 'insight' }">
          <span>{{ t('insight') }}</span>
        </RouterLink>
      </nav>
      <div v-if="progress" class="sidebar-progress">
        <span>{{ t('coverage') }}</span>
        <strong>{{ progress.attempted_questions }}<small>/ {{ progress.question_count }}</small></strong>
        <div><i :style="{ width: `${Math.min(100, progress.attempted_questions / Math.max(1, progress.question_count) * 100)}%` }" /></div>
        <p>{{ t('attempts', { count: progress.total_attempts }) }}</p>
      </div>
      <p class="sidebar-credit"><span>{{ t('questionSources') }}</span><template v-if="isEi">Owner-provided 892 electronic-information Markdown bank.</template><template v-else>Thanks to Bilibili creator <strong>cxy</strong> for collecting and organizing the question bank.</template></p>
      <div class="sidebar-preferences">
        <div class="scheme-switcher" :aria-label="t('appearance')">
          <button type="button" :class="{ active: scheme === 'dark' }" :title="t('dark')" @click="setScheme('dark')">◐</button>
          <button type="button" :class="{ active: scheme === 'light' }" :title="t('light')" @click="setScheme('light')">☀</button>
        </div>
        <label><span class="sr-only">{{ t('language') }}</span><select :value="language" :aria-label="t('language')" @change="setLanguage(($event.target as HTMLSelectElement).value as UiLanguage)"><option value="en">EN</option><option value="zh-CN">中文</option><option value="ja">日本語</option></select></label>
      </div>
      <div class="account">
        <span>{{ username.slice(0, 1).toUpperCase() }}</span>
        <div><strong>{{ username }}</strong><button @click="logout">{{ t('signOut') }}</button></div>
      </div>
    </aside>
    <main><RouterView v-if="identityReady" /></main>
  </div>
</template>
