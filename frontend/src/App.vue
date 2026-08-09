<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Calendar, Clock, DataAnalysis, Guide, List, Setting } from '@element-plus/icons-vue'
import ActiveSession from './components/ActiveSession.vue'
import HeatmapGrid from './components/HeatmapGrid.vue'
import MetricCard from './components/MetricCard.vue'
import { api, post } from './lib/api'
import type { Overview } from './types'

const TrendsView = defineAsyncComponent(() => import('./views/TrendsView.vue'))
const HistoryView = defineAsyncComponent(() => import('./views/HistoryView.vue'))
const IssuesView = defineAsyncComponent(() => import('./views/IssuesView.vue'))
const KnowledgeView = defineAsyncComponent(() => import('./views/KnowledgeView.vue'))
const SettingsView = defineAsyncComponent(() => import('./views/SettingsView.vue'))

type PageName = 'today' | 'trends' | 'history' | 'issues' | 'knowledge' | 'settings'
const page = ref<PageName>('today')
const overview = ref<Overview | null>(null)
const loading = ref(true)
const username = ref('')
const nav = [
  { id: 'today', label: '今日', icon: Clock }, { id: 'trends', label: '趋势', icon: DataAnalysis },
  { id: 'history', label: '记录', icon: List }, { id: 'issues', label: '问题', icon: Guide },
  { id: 'knowledge', label: '知识', icon: Calendar }, { id: 'settings', label: '设置', icon: Setting },
] as const
const subjectLabels: Record<string, string> = { math: '数学', english: '英语', major: '专业课', training: '训练' }
const todayHours = computed(() => overview.value ? `${Math.floor(overview.value.today.minutes / 60)}h ${overview.value.today.minutes % 60}m` : '--')
const maxTodaySubject = computed(() => Math.max(1, ...(overview.value?.today_subject_totals.map((item) => item.minutes) || [])))

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
onMounted(load)
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand"><span class="brand-mark">L</span><div><strong>Learning OS</strong><small>PERSONAL SYSTEM</small></div></div>
      <nav><button v-for="item in nav" :key="item.id" :class="{ active: page === item.id }" @click="page = item.id"><el-icon><component :is="item.icon" /></el-icon><span>{{ item.label }}</span></button></nav>
      <div class="sidebar-user"><span>{{ username.slice(0, 1).toUpperCase() }}</span><div><b>{{ username }}</b><button @click="logout">退出登录</button></div></div>
    </aside>
    <main class="main-content" v-loading.fullscreen.lock="loading">
      <div class="mobile-header"><div class="brand"><span class="brand-mark">L</span><strong>Learning OS</strong></div><el-dropdown trigger="click"><el-button>菜单</el-button><template #dropdown><el-dropdown-menu><el-dropdown-item v-for="item in nav" :key="item.id" @click="page = item.id">{{ item.label }}</el-dropdown-item><el-dropdown-item divided @click="logout">退出</el-dropdown-item></el-dropdown-menu></template></el-dropdown></div>
      <template v-if="page === 'today'">
        <section class="hero"><div><span class="eyebrow">{{ new Date().toLocaleDateString('zh-CN', { weekday: 'long', month: 'long', day: 'numeric' }) }}</span><h1>今天，继续向前。</h1><p>清晰记录投入，诚实完成复盘，让长期进步有迹可循。</p></div><div class="hero-date"><b>{{ new Date().getDate() }}</b><span>{{ new Date().toLocaleDateString('zh-CN', { month: 'short' }) }}</span></div></section>
        <ActiveSession :session="overview?.active_session || null" @changed="load" />
        <section v-if="overview" class="metrics-grid">
          <MetricCard label="今日学习" :value="todayHours" :hint="`首次开始 ${overview.today.first_start || '--'}`" tone="goal" />
          <MetricCard label="当前连续日" :value="overview.summary.current_streak" suffix="天" :hint="`历史最长 ${overview.summary.longest_streak} 天`" />
          <MetricCard label="连续 ≥5 小时" :value="overview.summary.current_five_hour_streak" suffix="天" :hint="`历史最长 ${overview.summary.longest_five_hour_streak} 天`" tone="goal" />
          <MetricCard label="5 小时达标日" :value="overview.summary.five_hour_days" suffix="天" hint="最近 180 天" tone="warm" />
          <MetricCard label="平均开始时间" :value="overview.summary.average_start_time || '--'" hint="按每日首次学习计算" tone="blue" />
          <MetricCard label="活跃学习日" :value="overview.summary.active_days" suffix="天" :hint="`${overview.summary.session_count} 次完成记录`" />
        </section>
        <section v-if="overview" class="panel subject-strip">
          <div><span class="eyebrow">TODAY BY SUBJECT</span><h2>今日科目分配</h2></div>
          <div class="subject-bars"><article v-for="item in overview.today_subject_totals" :key="item.subject"><span>{{ subjectLabels[item.subject] }}</span><div><i :class="`subject-${item.subject}`" :style="{ width: `${Math.max(item.minutes ? 5 : 0, item.minutes / maxTodaySubject * 100)}%` }" /></div><b>{{ item.minutes }}m</b></article></div>
        </section>
        <HeatmapGrid v-if="overview" :days="overview.heatmap" />
      </template>
      <TrendsView v-else-if="page === 'trends'" :overview="overview" />
      <HistoryView v-else-if="page === 'history'" />
      <IssuesView v-else-if="page === 'issues'" />
      <KnowledgeView v-else-if="page === 'knowledge'" />
      <SettingsView v-else />
    </main>
  </div>
</template>
