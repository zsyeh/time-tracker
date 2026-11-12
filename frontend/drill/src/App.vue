<script setup lang="ts">
import {computed,onMounted,onUnmounted,ref,watch} from 'vue'
import {useRoute,useRouter} from 'vue-router'
import {Grid,Clock,TrendCharts,MoreFilled,Setting,Menu,Collection,Document,Star,Refresh,DataAnalysis} from '@element-plus/icons-vue'
import {startLearningRecovery} from '../../shared/learningRecovery'
import AppSidebar from '../../shared/ui/navigation/AppSidebar.vue'
import NavigationItem from '../../shared/ui/navigation/NavigationItem.vue'
import AppHeader from '../../shared/ui/layout/AppHeader.vue'
import UiPopover from '../../shared/ui/UiPopover.vue'
import UiMenu from '../../shared/ui/UiMenu.vue'
import {api,post} from './lib/api'
import {configureWorkspaceScope} from './lib/workspace'
import {runtimeWorkspace} from './lib/runtimePath'
import {useUiPreferences} from './lib/uiPreferences'
import {uiText} from './lib/uiText'
import {activeDestination} from './lib/navigation'
const route=useRoute(),router=useRouter(),{t}=useUiPreferences()
let stopRecovery:(()=>void)|undefined
const username=ref(''),identityReady=ref(false),sidebarOpen=ref(false),moreToolsOpen=ref(false),accountOpen=ref(false)
const moreToolsTrigger=ref<HTMLElement|null>(null),accountTrigger=ref<HTMLElement|null>(null)
const stateKey='drill.sidebar.collapsed.v1'
function stored(){try{const value=localStorage.getItem(stateKey);return value===null?null:value==='true'}catch{return null}}
const preference=stored(),hasPreference=ref(preference!==null),sidebarCollapsed=ref(preference??route.name==='question')
const isEi=runtimeWorkspace==='ei'
const destination=computed(()=>activeDestination(route.name,route.query))
const primary=computed(()=>[
 {to:isEi?'/core-heatmap':'/selected-heatmap',label:isEi?uiText('五科核心热力图'):t('selectedHeatmap'),icon:Grid},
 {to:'/insight',label:t('insight'),icon:Clock},
 {to:'/progress',label:uiText('学习进度'),icon:TrendCharts},
 ...(isEi?[{to:'/cockpit',label:uiText('892 总览'),icon:DataAnalysis}]:[]),
])
const secondary=computed(()=>[
 {to:'/practice',label:t('practice'),icon:Collection},
 {to:'/diagnostics',label:uiText('解题能力'),icon:DataAnalysis},
 ...(isEi?[
  {to:'/circuit-selected',label:uiText('电路严选'),icon:Document},{to:'/signal-selected',label:uiText('信号严选'),icon:Document},
  {to:'/signal-formulas',label:uiText('892 每日公式'),icon:Document},{to:'/analog-selected',label:uiText('模电严选'),icon:Document},
  {to:'/digital-selected',label:uiText('数电严选'),icon:Document},{to:'/communication-selected',label:uiText('通信严选'),icon:Document},
  {to:'/selected-pdf-pages',label:uiText('严选题 PDF 页码记录'),icon:Document},
 ]:[]),
 {to:'/activity',label:t('activity'),icon:Clock},{to:'/book-activity',label:t('bookActivity'),icon:Document},
 {to:'/heatmap',label:t('knowledge'),icon:Grid},{to:'/papers',label:t('buildPaper'),icon:Document},
 {to:'/favorites',label:t('favorites'),icon:Star},{to:'/review-later',label:t('nextTime'),icon:Refresh},
 {to:'/feel',label:t('bookFeel'),icon:Document},{to:'/errata',label:uiText('勘误'),icon:Document},
])
const moreToolsActive=computed(()=>secondary.value.some(item=>item.to===`/${destination.value}`))
function collapse(value:boolean){sidebarCollapsed.value=value;hasPreference.value=true;try{localStorage.setItem(stateKey,String(value))}catch{}}
function toggleNavigation(){if(window.innerWidth<900)sidebarOpen.value=!sidebarOpen.value;else collapse(!sidebarCollapsed.value)}
async function logout(){await post('/api/auth/logout/',{});location.assign('/accounts/login/')}
const accountItems=computed(()=>[{id:'settings',label:uiText('设置'),run:()=>router.push('/settings')},{id:'logout',label:t('signOut'),run:()=>{void logout()}}])
watch(()=>route.fullPath,()=>{sidebarOpen.value=false;moreToolsOpen.value=false;accountOpen.value=false;if(!hasPreference.value)sidebarCollapsed.value=route.name==='question'})
onMounted(async()=>{document.title=isEi?'EI · 892 Practice':'Drill · Question Practice';const auth=await api<{user:{username:string;id?:number}}>('/api/auth/session/');configureWorkspaceScope(`${runtimeWorkspace}:${auth.user.username}`,auth.user.username);username.value=auth.user.username;stopRecovery=await startLearningRecovery(auth.user.id??auth.user.username,runtimeWorkspace,router,api);identityReady.value=true})
onUnmounted(()=>stopRecovery?.())
</script>
<template>
  <div class="drill-shell" :class="{'sidebar-collapsed':sidebarCollapsed,'ei-workspace':isEi,'question-route':route.name==='question'}">
    <AppSidebar :collapsed="sidebarCollapsed" v-model:mobile-open="sidebarOpen" :label="isEi?'EI navigation':'Drill navigation'" @update:collapsed="collapse">
      <template #workspace><RouterLink class="workspace-title" to="/practice">{{ isEi?'EI · 892':'Drill' }}</RouterLink></template>
      <template #primary><nav class="workspace-links" :aria-label="uiText('切换学习空间')"><a href="https://47.95.10.128/today">Timer</a><a href="https://47.95.10.128/drill/practice" :aria-current="!isEi?'page':undefined">Drill</a><a href="https://47.95.10.128/ei/practice" :aria-current="isEi?'page':undefined">EI</a></nav><nav class="primary-navigation" :aria-label="uiText('常用页面')"><NavigationItem v-for="item in primary" :key="item.to" :to="item.to" :label="item.label" :icon="item.icon" :active="item.to===`/${destination}`"/></nav></template>
      <template #secondary><button ref="moreToolsTrigger" type="button" class="more-tools-trigger" :class="{active:moreToolsActive||moreToolsOpen}" aria-controls="more-tools-panel" :aria-expanded="moreToolsOpen" @click="moreToolsOpen=!moreToolsOpen"><MoreFilled aria-hidden="true"/><span>{{ uiText('更多工具') }}</span></button><UiPopover v-model:open="moreToolsOpen" :anchor="moreToolsTrigger" id="more-tools-panel" :label="uiText('更多工具')"><nav class="more-tools-navigation"><NavigationItem v-for="item in secondary" :key="item.to" :to="item.to" :label="item.label" :icon="item.icon" :active="item.to===`/${destination}`"/></nav></UiPopover></template>
      <template #footer><button ref="accountTrigger" type="button" class="workspace-account" aria-haspopup="menu" :aria-expanded="accountOpen" @click="accountOpen=!accountOpen"><span>{{ username.slice(0,1).toUpperCase() }}</span><strong>{{ username }}</strong><Setting aria-hidden="true"/></button><UiMenu v-model:open="accountOpen" :anchor="accountTrigger" :items="accountItems" :label="uiText('账户')"/></template>
    </AppSidebar>
    <main><AppHeader v-if="route.name!=='question'" :title="isEi?'EI · 892':'Drill'" nav-toggle @toggle="toggleNavigation"/><button v-else type="button" class="question-navigation-toggle ui-icon-button" aria-label="打开导航" @click="toggleNavigation"><Menu aria-hidden="true"/></button><RouterView v-if="identityReady"/></main>
  </div>
</template>
