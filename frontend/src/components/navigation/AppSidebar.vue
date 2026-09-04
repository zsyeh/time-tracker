<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Clock, DataAnalysis, Expand, Fold, Guide, List, Setting } from '@element-plus/icons-vue'
import GlobalSearch from '../GlobalSearch.vue'
import SidebarItem from './SidebarItem.vue'
import SidebarSection from './SidebarSection.vue'
import WorkspaceSwitcher from './WorkspaceSwitcher.vue'

const props = defineProps<{ username: string; collapsed: boolean }>()
const emit = defineEmits<{ 'update:collapsed': [value: boolean]; logout: [] }>()
const route = useRoute()
const mobileOpen = ref(false)
const activeSection = computed(() => route.name === 'session-detail' ? 'sessions' : route.name)
const activeSubject = computed(() => String(route.query.subject || ''))

watch(() => route.fullPath, () => { mobileOpen.value = false })
</script>

<template>
  <button v-if="collapsed" type="button" class="sidebar-reopen" aria-label="Show sidebar" @click="emit('update:collapsed', false)"><el-icon><Expand /></el-icon></button>
  <button type="button" class="mobile-sidebar-open" aria-label="Open navigation" aria-controls="app-sidebar" :aria-expanded="mobileOpen" @click="mobileOpen = true"><el-icon><Expand /></el-icon></button>
  <button v-if="mobileOpen" type="button" class="sidebar-backdrop" aria-label="Close navigation" @click="mobileOpen = false" />

  <aside id="app-sidebar" class="sidebar" :class="{ 'mobile-open': mobileOpen }">
    <div class="sidebar-topline"><WorkspaceSwitcher /><button type="button" class="mobile-sidebar-close" aria-label="Close navigation" @click="mobileOpen = false">×</button></div>
    <GlobalSearch />

    <nav class="sidebar-navigation" aria-label="Primary navigation">
      <SidebarItem label="Today" to="/today" :icon="Clock" :active="activeSection === 'today'" />
      <SidebarSection title="Workspace" storage-key="learning-os.sidebar.workspace">
        <SidebarItem label="Trends" to="/trends" :icon="DataAnalysis" :active="activeSection === 'trends'" />
        <SidebarItem label="Sessions" to="/sessions" :icon="List" :active="activeSection === 'sessions' && !activeSubject" />
        <SidebarItem label="Issues" to="/issues" :icon="Guide" :active="activeSection === 'issues'" />
      </SidebarSection>
      <SidebarSection title="Subjects" storage-key="learning-os.sidebar.subjects">
        <SidebarItem label="Mathematics" :to="{ path: '/sessions', query: { subject: 'math' } }" :active="activeSection === 'sessions' && activeSubject === 'math'" />
        <SidebarItem label="English" :to="{ path: '/sessions', query: { subject: 'english' } }" :active="activeSection === 'sessions' && activeSubject === 'english'" />
        <SidebarItem label="Major / 892" :to="{ path: '/sessions', query: { subject: 'major' } }" :active="activeSection === 'sessions' && activeSubject === 'major'" />
        <SidebarItem label="Training" :to="{ path: '/sessions', query: { subject: 'training' } }" :active="activeSection === 'sessions' && activeSubject === 'training'" />
      </SidebarSection>
    </nav>

    <div class="sidebar-spacer" />
    <nav class="sidebar-utilities" aria-label="Utility navigation">
      <SidebarItem label="Settings" to="/settings" :icon="Setting" :active="activeSection === 'settings'" />
      <button type="button" class="sidebar-collapse" @click="emit('update:collapsed', true)"><el-icon><Fold /></el-icon><span>Hide sidebar</span></button>
    </nav>
    <div class="sidebar-account"><span>{{ username.slice(0, 1).toUpperCase() }}</span><div><strong>{{ username }}</strong><button type="button" @click="emit('logout')">Sign out</button></div></div>
  </aside>
</template>
