<script setup lang="ts">
import { computed, defineAsyncComponent, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Clock, DataAnalysis, Guide, List, Search as SearchIcon, Setting } from '@element-plus/icons-vue'
import BrandIdentity from './components/BrandIdentity.vue'
import GlobalSearch from './components/GlobalSearch.vue'
import { api, post } from './lib/api'
import { mathVisualizationEnabled } from './lib/featureFlags'
import type { Overview } from './types'
import type { FormulaLaunchRequest } from './math-visualizer/core/formulaRouter'

const MathLabView = defineAsyncComponent(() => import('./views/MathLabView.vue'))
const route = useRoute()
const router = useRouter()
const overview = ref<Overview | null>(null)
const loading = ref(false)
const username = ref('')
const globalSearch = ref<InstanceType<typeof GlobalSearch> | null>(null)
const mathLabLaunch = ref<FormulaLaunchRequest | null>(null)
const mathLabOpen = ref(false)
const mathLabDialog = ref<HTMLDialogElement | null>(null)
let mathLabReturnTarget: HTMLElement | null = null

const nav = [
  { id: 'today', label: 'Today', icon: Clock, to: '/today' },
  { id: 'trends', label: 'Trends', icon: DataAnalysis, to: '/trends' },
  { id: 'sessions', label: 'Sessions', icon: List, to: '/sessions' },
  { id: 'issues', label: 'Issues', icon: Guide, to: '/issues' },
  { id: 'settings', label: 'Settings', icon: Setting, to: '/settings' },
] as const

const activeSection = computed(() => route.name === 'session-detail' ? 'sessions' : route.name)
const isPublicRoute = computed(() => route.meta.public === true)

async function load() {
  loading.value = true
  try {
    const [data, auth] = await Promise.all([
      api<Overview>('/api/dashboard/overview/?days=180'),
      api<{ user: { username: string } }>('/api/auth/session/'),
    ])
    overview.value = data
    mathVisualizationEnabled.value = Boolean(data.features?.math_visualization)
    username.value = auth.user.username
  } catch (error) { ElMessage.error((error as Error).message) } finally { loading.value = false }
}

async function logout() { await post('/api/auth/logout/'); location.assign('/accounts/login/') }

async function openMathLab(event: Event) {
  if (!mathVisualizationEnabled.value) return
  const request = (event as CustomEvent<FormulaLaunchRequest>).detail
  if (!request) return
  mathLabReturnTarget = document.activeElement instanceof HTMLElement ? document.activeElement : null
  mathLabLaunch.value = request
  mathLabOpen.value = true
  await nextTick()
  const dialog = mathLabDialog.value
  if (dialog && !dialog.open) {
    try { dialog.showModal() } catch { dialog.setAttribute('open', '') }
  }
}

function closeMathLab() {
  const dialog = mathLabDialog.value
  if (dialog?.open) dialog.close()
  else onMathLabDialogClose()
}

function onMathLabDialogClose() {
  mathLabOpen.value = false
  mathLabLaunch.value = null
  const target = mathLabReturnTarget
  mathLabReturnTarget = null
  requestAnimationFrame(() => target?.focus({ preventScroll: true }))
}

watch(isPublicRoute, (isPublic) => {
  if (!isPublic && !overview.value) void load()
}, { immediate: true })

onMounted(() => window.addEventListener('learning-os-open-math-lab', openMathLab))
onBeforeUnmount(() => {
  window.removeEventListener('learning-os-open-math-lab', openMathLab)
  if (mathLabDialog.value?.open) mathLabDialog.value.close()
})
</script>

<template>
  <div v-if="isPublicRoute" class="public-app-shell">
    <RouterView />
  </div>

  <div v-else class="app-shell">
    <aside class="sidebar">
      <BrandIdentity />
      <GlobalSearch ref="globalSearch" />
      <nav aria-label="Primary navigation"><span class="nav-section">Workspace</span><RouterLink v-for="item in nav" :key="item.id" :to="item.to" :class="{ active: activeSection === item.id }"><el-icon><component :is="item.icon" /></el-icon><span>{{ item.label }}</span></RouterLink></nav>
      <div class="sidebar-user"><span>{{ username.slice(0, 1).toUpperCase() }}</span><div><b>{{ username }}</b><button @click="logout">Sign out</button></div></div>
    </aside>
    <main class="main-content" v-loading.fullscreen.lock="loading">
      <div class="mobile-header"><BrandIdentity /><div class="mobile-tools"><el-button circle aria-label="Open global search" @click="globalSearch?.open()"><el-icon><SearchIcon /></el-icon></el-button><el-dropdown trigger="click"><el-button>Menu</el-button><template #dropdown><el-dropdown-menu><el-dropdown-item v-for="item in nav" :key="item.id" @click="router.push(item.to)">{{ item.label }}</el-dropdown-item><el-dropdown-item divided @click="logout">Sign out</el-dropdown-item></el-dropdown-menu></template></el-dropdown></div></div>
      <RouterView v-slot="{ Component }">
        <component v-if="route.name === 'today' || route.name === 'trends'" :is="Component" :overview="overview" @changed="load" />
        <component v-else-if="route.name === 'settings'" :is="Component" @changed="load" />
        <component v-else :is="Component" />
      </RouterView>
    </main>
  </div>

  <Teleport to="body">
    <dialog v-if="mathLabOpen" ref="mathLabDialog" class="math-lab-window" aria-label="Formula visualization window" @cancel.prevent="closeMathLab" @close="onMathLabDialogClose">
      <div class="math-lab-window-frame">
        <Suspense><MathLabView :launch-request="mathLabLaunch" @close="closeMathLab" /><template #fallback><div class="math-window-loader">OPENING VISUALIZATION…</div></template></Suspense>
      </div>
    </dialog>
  </Teleport>
</template>
