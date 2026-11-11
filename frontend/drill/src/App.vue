<script setup lang="ts">
import { uiText } from './lib/uiText'
import { startLearningRecovery } from '../../shared/learningRecovery'
import { useRouter } from 'vue-router'
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api, post } from './lib/api'
import { configureWorkspaceScope } from './lib/workspace'
import type { Progress } from './types'
import { useUiPreferences, type UiLanguage } from './lib/uiPreferences'
import { runtimeWorkspace } from './lib/runtimePath'

const route = useRoute()
const recoveryRouter = useRouter()
let stopRecovery: (() => void) | undefined
const username = ref('')
const progress = ref<Progress | null>(null)
const sidebarOpen = ref(false)
const moreToolsOpen = ref(false)
const moreToolsTrigger = ref<HTMLButtonElement | null>(null)
const moreToolsPanel = ref<HTMLElement | null>(null)
const moreToolsStyle = ref<Record<string, string>>({})
const moreToolsActive = computed(() => {
  const name = String(route.name || '')
  if (name === 'question') {
    const from = String(route.query.from || '')
    const collection = String(route.query.collection || '')
    return !from || from === 'heatmap' || from === 'collection' ||
      ['circuit_selected', 'signal_selected', 'analog_selected', 'digital_selected', 'communication_selected'].includes(collection)
  }
  return name.startsWith('paper') || [
    'practice', 'activity', 'book-activity', 'heatmap', 'favorites', 'review-later', 'feel', 'errata',
    'circuit-selected', 'signal-selected', 'signal-formulas', 'analog-selected',
    'digital-selected', 'communication-selected', 'selected-pdf-pages',
  ].includes(name)
})
const identityReady = ref(false)
const sidebarStateKey = 'drill.sidebar.collapsed.v1'
const storedSidebarState = (() => {
  try {
    const value = localStorage.getItem(sidebarStateKey)
    return value === null ? null : value === 'true'
  } catch {
    return null
  }
})()
const hasSidebarPreference = ref(storedSidebarState !== null)
const sidebarCollapsed = ref(storedSidebarState ?? route.name === 'question')
const isEi = runtimeWorkspace === 'ei'
const workspaceIcon = '/static/drill/drill-icon-180.png?v=img9392'
const { language, scheme, setLanguage, setScheme, t } = useUiPreferences()

document.title = isEi ? 'EI · 892 Practice' : 'Drill · Question Practice'

async function loadIdentity() {
  const auth = await api<{ user: { username: string; id?: number } }>('/api/auth/session/')
  configureWorkspaceScope(`${runtimeWorkspace}:${auth.user.username}`, auth.user.username)
  username.value = auth.user.username
  stopRecovery = await startLearningRecovery(auth.user.id ?? auth.user.username, runtimeWorkspace, recoveryRouter, api)
  identityReady.value = true
  progress.value = await api<Progress>('/api/drill/progress/')
}

async function logout() {
  await post('/api/auth/logout/', {})
  location.assign('/accounts/login/')
}

function setSidebarCollapsed(value: boolean) {
  moreToolsOpen.value = false
  sidebarCollapsed.value = value
  hasSidebarPreference.value = true
  try { localStorage.setItem(sidebarStateKey, String(value)) } catch { /* Keep the in-memory preference. */ }
}

watch(() => route.fullPath, () => {
  sidebarOpen.value = false
  moreToolsOpen.value = false
  if (!hasSidebarPreference.value) sidebarCollapsed.value = route.name === 'question'
})

function positionMoreTools() {
  if (!moreToolsOpen.value || !moreToolsTrigger.value) return
  const anchor = moreToolsTrigger.value.getBoundingClientRect()
  const viewportWidth = document.documentElement.clientWidth || window.innerWidth
  const viewportHeight = window.visualViewport?.height ?? window.innerHeight
  const width = Math.min(272, viewportWidth - 24)
  const desktop = viewportWidth > 900
  const left = desktop
    ? Math.min(anchor.right + 8, viewportWidth - width - 12)
    : Math.max(12, Math.min(anchor.left, viewportWidth - width - 12))
  const roomBelow = viewportHeight - anchor.bottom - 20
  const top = desktop
    ? Math.max(12, Math.min(anchor.top, viewportHeight - 300))
    : roomBelow >= 240 ? anchor.bottom + 8 : 12
  const maxHeight = !desktop && roomBelow < 240
    ? Math.max(180, anchor.top - 24)
    : Math.max(180, Math.min(520, viewportHeight - top - 12))
  moreToolsStyle.value = {
    left: `${left}px`,
    top: `${top}px`,
    width: `${width}px`,
    maxHeight: `${maxHeight}px`,
  }
}

async function toggleMoreTools() {
  moreToolsOpen.value = !moreToolsOpen.value
  if (moreToolsOpen.value) {
    await nextTick()
    positionMoreTools()
    const firstLink = moreToolsPanel.value?.querySelector<HTMLAnchorElement>('a.active') ||
      moreToolsPanel.value?.querySelector<HTMLAnchorElement>('a')
    firstLink?.focus()
  }
}

function closeMoreToolsOnOutside(event: PointerEvent) {
  const target = event.target
  if (target instanceof Node && (moreToolsTrigger.value?.contains(target) || moreToolsPanel.value?.contains(target))) return
  moreToolsOpen.value = false
}

function closeMoreToolsOnEscape(event: KeyboardEvent) {
  if (event.key !== 'Escape' || !moreToolsOpen.value) return
  moreToolsOpen.value = false
  moreToolsTrigger.value?.focus()
}

onMounted(() => {
  void loadIdentity()
  document.addEventListener('pointerdown', closeMoreToolsOnOutside)
  document.addEventListener('keydown', closeMoreToolsOnEscape)
  window.addEventListener('resize', positionMoreTools)
  window.visualViewport?.addEventListener('resize', positionMoreTools)
})
onUnmounted(() => {
  stopRecovery?.()
  document.removeEventListener('pointerdown', closeMoreToolsOnOutside)
  document.removeEventListener('keydown', closeMoreToolsOnEscape)
  window.removeEventListener('resize', positionMoreTools)
  window.visualViewport?.removeEventListener('resize', positionMoreTools)
})
</script>

<template>
  <div class="drill-shell" :class="{ 'drawer-open': sidebarOpen, 'sidebar-collapsed': sidebarCollapsed, 'ei-workspace': isEi, 'question-route': route.name === 'question' }">
    <button class="drawer-toggle" type="button" aria-label="Open navigation" aria-controls="drill-navigation" :aria-expanded="sidebarOpen" @click="sidebarOpen = true"><span /><span /><span /></button>
    <button class="sidebar-expand" type="button" aria-label="Show sidebar" title="Show sidebar" @click="setSidebarCollapsed(false)"><span /><span /><span /></button>
    <button v-if="sidebarOpen" class="drawer-backdrop" type="button" aria-label="Close navigation" @click="sidebarOpen = false" />
    <aside id="drill-navigation" class="drill-sidebar">
      <button class="drawer-close" type="button" aria-label="Close navigation" @click="sidebarOpen = false">×</button>
      <button class="sidebar-collapse" type="button" aria-label="Hide sidebar" title="Hide sidebar" @click="setSidebarCollapsed(true)">‹</button>
      <RouterLink class="wordmark" to="/practice" aria-label="Drill home">
        <img :src="workspaceIcon" alt="" aria-hidden="true" /><strong>{{ isEi ? '892 LAB' : 'DRILL' }}</strong><small>{{ isEi ? 'ELECTRONIC INFORMATION' : 'QUESTION PRACTICE' }}</small>
      </RouterLink>
      <nav class="workspace-links" :aria-label="uiText('切换学习空间')">
        <a href="https://47.95.10.128/today">Timer</a>
        <a href="https://47.95.10.128/drill/practice" :aria-current="!isEi ? 'page' : undefined">Drill</a>
        <a href="https://47.95.10.128/ei/practice" :aria-current="isEi ? 'page' : undefined">EI</a>
      </nav>
      <nav class="primary-navigation" :aria-label="uiText('常用页面')">
        <span class="navigation-heading">{{ uiText('常用页面') }}</span>
        <RouterLink v-if="!isEi" to="/selected-heatmap" :class="{ active: route.name === 'selected-heatmap' || (route.name === 'question' && route.query.from === 'selected-heatmap') }">
          <span>{{ t('selectedHeatmap') }}</span>
        </RouterLink>
        <RouterLink v-if="isEi" to="/cockpit" :class="{ active: route.name === 'cockpit' || (route.name === 'question' && route.query.from === 'cockpit') }">
          <span>{{ uiText("892 总览") }}</span>
        </RouterLink>
        <RouterLink v-if="isEi" to="/core-heatmap" :class="{ active: route.name === 'core-heatmap' || (route.name === 'question' && route.query.from === 'core-heatmap') }"><span>{{ uiText("五科核心热力图") }}</span></RouterLink>
        <RouterLink to="/insight" :class="{ active: route.name === 'insight' || (route.name === 'question' && route.query.from === 'insight') }"><span>{{ t('insight') }}</span></RouterLink>
        <RouterLink to="/diagnostics" :class="{ active: route.name === 'diagnostics' || route.name === 'diagnostic-queue' || (route.name === 'question' && route.query.from === 'diagnostics') }"><span>{{ uiText("解题能力") }}</span></RouterLink>
      </nav>
      <div class="more-tools-group">
        <button ref="moreToolsTrigger" class="more-tools-trigger" :class="{ active: moreToolsActive || moreToolsOpen }" type="button" aria-controls="more-tools-panel" :aria-expanded="moreToolsOpen" @click="toggleMoreTools">
          <span class="more-tools-trigger-icon" aria-hidden="true">•••</span><span>{{ uiText('更多工具') }}</span><span class="more-tools-chevron" aria-hidden="true">⌄</span>
        </button>
      </div>
      <Teleport to="body">
      <nav v-if="moreToolsOpen" id="more-tools-panel" ref="moreToolsPanel" class="more-tools-panel" :class="{ 'ei-workspace': isEi }" :style="moreToolsStyle" :aria-label="uiText('更多工具')">
        <span class="more-tools-panel-heading">{{ uiText('更多工具') }}</span>
        <RouterLink to="/practice" :class="{ active: route.name === 'practice' || (route.name === 'question' && !route.query.from) }">
          <span>{{ t('practice') }}</span>
        </RouterLink>
        <RouterLink v-if="isEi" to="/circuit-selected" :class="{ active: route.name === 'circuit-selected' || (route.name === 'question' && route.query.collection === 'circuit_selected') }"><span>{{ uiText("电路严选") }}</span></RouterLink>
        <RouterLink v-if="isEi" to="/signal-selected" :class="{ active: route.name === 'signal-selected' || (route.name === 'question' && route.query.collection === 'signal_selected') }"><span>{{ uiText("信号严选") }}</span></RouterLink>
        <RouterLink v-if="isEi" to="/signal-formulas" :class="{ active: route.name === 'signal-formulas' }"><span>{{ uiText("892 每日公式") }}</span></RouterLink>
        <RouterLink v-if="isEi" to="/analog-selected" :class="{ active: route.name === 'analog-selected' || (route.name === 'question' && route.query.collection === 'analog_selected') }"><span>{{ uiText("模电严选") }}</span></RouterLink>
        <RouterLink v-if="isEi" to="/digital-selected" :class="{ active: route.name === 'digital-selected' || (route.name === 'question' && route.query.collection === 'digital_selected') }"><span>{{ uiText("数电严选") }}</span></RouterLink>
        <RouterLink v-if="isEi" to="/communication-selected" :class="{ active: route.name === 'communication-selected' || (route.name === 'question' && route.query.collection === 'communication_selected') }"><span>{{ uiText("通信严选") }}</span></RouterLink>
        <RouterLink v-if="isEi" to="/selected-pdf-pages" :class="{ active: route.name === 'selected-pdf-pages' }"><span>{{ uiText("严选题 PDF 页码记录") }}</span></RouterLink>
        <RouterLink to="/activity" :class="{ active: route.name === 'activity' }">
          <span>{{ t('activity') }}</span>
        </RouterLink>
        <RouterLink to="/book-activity" :class="{ active: route.name === 'book-activity' }">
          <span>{{ t('bookActivity') }}</span>
        </RouterLink>
        <RouterLink to="/heatmap" :class="{ active: route.name === 'heatmap' || (route.name === 'question' && route.query.from === 'heatmap') }">
          <span>{{ t('knowledge') }}</span>
        </RouterLink>
        <RouterLink to="/papers" :class="{ active: String(route.name || '').startsWith('paper') }">
          <span>{{ t('buildPaper') }}</span>
        </RouterLink>
        <RouterLink to="/favorites" :class="{ active: route.name === 'favorites' || (route.name === 'question' && route.query.from === 'collection' && route.query.collection === 'favorite') }">
          <span>{{ t('favorites') }}</span>
        </RouterLink>
        <RouterLink to="/review-later" :class="{ active: route.name === 'review-later' || (route.name === 'question' && route.query.from === 'collection' && route.query.collection === 'review_later') }">
          <span>{{ t('nextTime') }}</span>
        </RouterLink>
        <RouterLink to="/feel" :class="{ active: route.name === 'feel' }">
          <span>{{ t('bookFeel') }}</span>
        </RouterLink>
        <RouterLink to="/errata" :class="{ active: route.name === 'errata' }">
          <span>{{ uiText("勘误") }}</span>
        </RouterLink>
      </nav>
      </Teleport>
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
