<script setup lang="ts">
import { computed, defineAsyncComponent, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Clock, DataAnalysis, Guide, List, Search as SearchIcon, Setting } from '@element-plus/icons-vue'
import ActiveSession from './components/ActiveSession.vue'
import GlobalSearch from './components/GlobalSearch.vue'
import HeatmapGrid from './components/HeatmapGrid.vue'
import MetricCard from './components/MetricCard.vue'
import { api, post } from './lib/api'
import type { Overview } from './types'
import type { FormulaLaunchRequest } from './math-visualizer/core/formulaRouter'

const TrendsView = defineAsyncComponent(() => import('./views/TrendsView.vue'))
const HistoryView = defineAsyncComponent(() => import('./views/HistoryView.vue'))
const IssuesView = defineAsyncComponent(() => import('./views/IssuesView.vue'))
const MathLabView = defineAsyncComponent(() => import('./views/MathLabView.vue'))
const SettingsView = defineAsyncComponent(() => import('./views/SettingsView.vue'))

type PageName = 'today' | 'trends' | 'history' | 'issues' | 'settings'
const page = ref<PageName>('today')
const overview = ref<Overview | null>(null)
const loading = ref(true)
const username = ref('')
const globalSearch = ref<InstanceType<typeof GlobalSearch> | null>(null)
const mathLabLaunch = ref<FormulaLaunchRequest | null>(null)
const mathLabOpen = ref(false)
const mathLabDialog = ref<HTMLDialogElement | null>(null)
let mathLabReturnTarget: HTMLElement | null = null
const nav = [
  { id: 'today', label: 'Today', icon: Clock }, { id: 'trends', label: 'Trends', icon: DataAnalysis },
  { id: 'history', label: 'Sessions', icon: List }, { id: 'issues', label: 'Issues', icon: Guide },
  { id: 'settings', label: 'Settings', icon: Setting },
] as const
const subjectLabels: Record<string, string> = { math: 'Mathematics', english: 'English', major: 'Major', training: 'Training' }
const todayHours = computed(() => overview.value ? `${Math.floor(overview.value.today.minutes / 60)}h ${overview.value.today.minutes % 60}m` : '--')
const maxTodaySubject = computed(() => Math.max(1, ...(overview.value?.today_subject_totals.map((item) => item.minutes) || [])))
const todayProgress = computed(() => Math.min(100, Math.round((overview.value?.today.minutes || 0) / 300 * 100)))
const statusLabel = computed(() => todayProgress.value >= 100 ? 'TARGET MET' : overview.value?.active_session ? 'SESSION ACTIVE' : 'NO ACTIVE SESSION')
const todayLabel = computed(() => overview.value?.calendar.today.replaceAll('-', '.') || '----.--.--')
const weekdayLabel = computed(() => {
  if (!overview.value) return 'TODAY'
  return new Intl.DateTimeFormat('en-US', { weekday: 'long', timeZone: 'Asia/Shanghai' })
    .format(new Date(`${overview.value.calendar.today}T12:00:00+08:00`)).toUpperCase()
})

async function load() {
  loading.value = true
  try {
    const [data, auth] = await Promise.all([
      api<Overview>('/api/dashboard/overview/?days=180'),
      api<{ user: { username: string } }>('/api/auth/session/'),
    ])
    overview.value = data
    username.value = auth.user.username
  } catch (error) { ElMessage.error((error as Error).message) } finally { loading.value = false }
}
async function logout() { await post('/api/auth/logout/'); location.assign('/accounts/login/') }
async function openMathLab(event: Event) {
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
onMounted(() => { window.addEventListener('learning-os-open-math-lab', openMathLab); void load() })
onBeforeUnmount(() => { window.removeEventListener('learning-os-open-math-lab', openMathLab); if (mathLabDialog.value?.open) mathLabDialog.value.close() })
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand"><span class="brand-mark">L</span><div><strong>Learning OS</strong><small>PERSONAL SYSTEM</small></div></div>
      <GlobalSearch ref="globalSearch" @navigate="page = $event" />
      <nav><span class="nav-section">WORKSPACE</span><button v-for="item in nav" :key="item.id" :class="{ active: page === item.id }" @click="page = item.id"><el-icon><component :is="item.icon" /></el-icon><span>{{ item.label }}</span></button></nav>
      <div class="sidebar-user"><span>{{ username.slice(0, 1).toUpperCase() }}</span><div><b>{{ username }}</b><button @click="logout">Sign out</button></div></div>
    </aside>
    <main class="main-content" v-loading.fullscreen.lock="loading">
      <div class="mobile-header"><div class="brand"><span class="brand-mark">L</span><strong>Learning OS</strong></div><div class="mobile-tools"><el-button circle aria-label="Open global search" @click="globalSearch?.open()"><el-icon><SearchIcon /></el-icon></el-button><el-dropdown trigger="click"><el-button>Menu</el-button><template #dropdown><el-dropdown-menu><el-dropdown-item v-for="item in nav" :key="item.id" @click="page = item.id">{{ item.label }}</el-dropdown-item><el-dropdown-item divided @click="logout">Sign out</el-dropdown-item></el-dropdown-menu></template></el-dropdown></div></div>
      <template v-if="page === 'today'">
        <section class="hero exam-hero">
          <div class="date-block"><span class="eyebrow">TODAY / {{ weekdayLabel }}</span><h1>{{ todayLabel }}</h1><p>LOCAL DATE · ASIA/SHANGHAI</p><p v-if="overview?.private_display.homepage_content" class="homepage-content">{{ overview.private_display.homepage_content }}</p><p v-if="overview?.private_display.study_room_code" class="study-room-code">STUDY ROOM · {{ overview.private_display.study_room_code }}</p></div>
          <div class="exam-countdown"><span>{{ overview?.private_display.countdown_label || '2026 POSTGRADUATE EXAM' }}</span><div><b>{{ overview?.calendar.days_until_exam ?? '--' }}</b><small>DAYS</small></div><time>{{ overview?.calendar.exam_date || '2026-12-26' }}</time></div>
        </section>
        <ActiveSession :session="overview?.active_session || null" @changed="load" />
        <section v-if="overview" class="status-overview panel">
          <div class="status-ring" :style="{ '--status-progress': `${todayProgress * 3.6}deg` }"><div><strong>{{ todayProgress }}</strong><span>%</span><small>5H TARGET</small></div></div>
          <div class="status-copy"><span class="eyebrow">DAILY STATUS</span><h2>{{ statusLabel }}</h2><p>Completed sessions only. Active duration remains hidden.</p></div>
          <dl><div><dt>FIRST START</dt><dd>{{ overview.today.first_start || '--' }}</dd></div><div><dt>SESSIONS</dt><dd>{{ overview.today.sessions }}</dd></div><div><dt>DATE</dt><dd>{{ overview.calendar.today.slice(5) }}</dd></div></dl>
        </section>
        <section v-if="overview" class="metrics-grid">
          <MetricCard label="TODAY" :value="todayHours" :hint="`First start ${overview.today.first_start || '--'}`" tone="goal" />
          <MetricCard label="CURRENT STREAK" :value="overview.summary.current_streak" suffix="days" :hint="`Longest ${overview.summary.longest_streak} days`" />
          <MetricCard label="5H STREAK" :value="overview.summary.current_five_hour_streak" suffix="days" :hint="`Longest ${overview.summary.longest_five_hour_streak} days`" tone="goal" />
          <MetricCard label="5H DAYS" :value="overview.summary.five_hour_days" suffix="days" hint="Last 180 days" tone="warm" />
          <MetricCard label="AVG. START" :value="overview.summary.average_start_time || '--'" hint="First session per active day" tone="blue" />
          <MetricCard label="ACTIVE DAYS" :value="overview.summary.active_days" suffix="days" :hint="`${overview.summary.session_count} completed sessions`" />
        </section>
        <section v-if="overview" class="panel subject-strip">
          <div><span class="eyebrow">BREAKDOWN</span><h2>Today by subject</h2></div>
          <div class="subject-bars"><article v-for="item in overview.today_subject_totals" :key="item.subject"><span>{{ subjectLabels[item.subject] }}</span><div><i :class="`subject-${item.subject}`" :style="{ width: `${Math.max(item.minutes ? 5 : 0, item.minutes / maxTodaySubject * 100)}%` }" /></div><b>{{ item.minutes }}m</b></article></div>
        </section>
        <HeatmapGrid v-if="overview" :days="overview.heatmap" />
      </template>
      <TrendsView v-else-if="page === 'trends'" :overview="overview" />
      <HistoryView v-else-if="page === 'history'" />
      <IssuesView v-else-if="page === 'issues'" />
      <SettingsView v-else @changed="load" />
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
