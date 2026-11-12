<script setup lang="ts">
import { useAccountPreferences } from '../shared/preferences/store'
import type { PreferenceSnapshot } from '../shared/preferences/schema'
import { computed, defineAsyncComponent, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import AppSidebar from './components/navigation/AppSidebar.vue'
import { api, post } from './lib/api'
import { startLearningRecovery } from '../shared/learningRecovery'
import { mathVisualizationEnabled } from './lib/featureFlags'
import type { Overview } from './types'
import type { FormulaLaunchRequest } from './math-visualizer/core/formulaRouter'

const MathLabView = defineAsyncComponent(() => import('./views/MathLabView.vue'))
const preferences=useAccountPreferences()
const route = useRoute()
const recoveryRouter = useRouter()
let stopRecovery: (() => void) | undefined
let recoveryStarted = false
const overview = ref<Overview | null>(null)
const loading = ref(false)
const username = ref('')
const identityReady = ref(false)
function readSidebarCollapsed() {
  try { return sessionStorage.getItem('learning-os.sidebar.window.v2.'+(preferences.userId.value||'session')) === 'true' }
  catch { return false }
}
const sidebarCollapsed = ref(readSidebarCollapsed())
const mathLabLaunch = ref<FormulaLaunchRequest | null>(null)
const mathLabOpen = ref(false)
const mathLabDialog = ref<HTMLDialogElement | null>(null)
let mathLabReturnTarget: HTMLElement | null = null

const isPublicRoute = computed(() => route.meta.public === true)

async function load() {
  loading.value = true
  try {
    const [data, auth] = await Promise.all([
      api<Overview>('/api/dashboard/overview/?days=180'),
      api<{ user: { username: string; id?: number };preferences?:PreferenceSnapshot }>('/api/auth/session/'),
    ])
    overview.value = data
    mathVisualizationEnabled.value = Boolean(data.features?.math_visualization)
    void preferences.bind(auth.user.id ?? auth.user.username,auth.preferences)
    username.value = auth.user.username
    if (!recoveryStarted) {
      recoveryStarted = true
      stopRecovery = await startLearningRecovery(auth.user.id ?? auth.user.username, 'timer', recoveryRouter, api)
    }
    identityReady.value = true
  } catch (error) { ElMessage.error((error as Error).message) } finally { loading.value = false }
}

async function logout() { await post('/api/auth/logout/'); preferences.reset(true); location.assign('/accounts/login/') }

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
watch(sidebarCollapsed, (value) => {
  try { sessionStorage.setItem('learning-os.sidebar.window.v2.'+(preferences.userId.value||'session'), String(value)) } catch { /* Storage may be unavailable. */ }
})

onMounted(() => window.addEventListener('learning-os-open-math-lab', openMathLab))
onBeforeUnmount(() => {
  stopRecovery?.()
  window.removeEventListener('learning-os-open-math-lab', openMathLab)
  if (mathLabDialog.value?.open) mathLabDialog.value.close()
})
</script>

<template>
  <div v-if="isPublicRoute" class="public-app-shell">
    <RouterView />
  </div>

  <div v-else class="app-shell" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
    <AppSidebar v-model:collapsed="sidebarCollapsed" :username="username" @logout="logout" />
    <main class="main-content" v-loading.fullscreen.lock="loading">
      <RouterView v-if="identityReady" v-slot="{ Component }">
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
