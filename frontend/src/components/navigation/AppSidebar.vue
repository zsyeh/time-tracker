<script setup lang="ts">
import{computed,onMounted,onUnmounted,ref,watch}from'vue'
import CustomizableNavigation from '../../../shared/ui/navigation/CustomizableNavigation.vue'
import {useAccountPreferences} from '../../../shared/preferences/store'
import{useRoute}from'vue-router'
import{Clock,DataAnalysis,List,Guide,Setting}from'@element-plus/icons-vue'
import SharedSidebar from '../../../shared/ui/navigation/AppSidebar.vue'
import NavigationItem from '../../../shared/ui/navigation/NavigationItem.vue'
import NavigationGroup from '../../../shared/ui/navigation/NavigationGroup.vue'
import UiMenu from '../../../shared/ui/UiMenu.vue'
import GlobalSearch from '../GlobalSearch.vue'
import{useUiPreferences}from'../../lib/uiPreferences'
const preferences=useAccountPreferences()
const props=defineProps<{username:string;collapsed:boolean}>();const emit=defineEmits<{'update:collapsed':[value:boolean];logout:[]}>()
const route=useRoute(),{t}=useUiPreferences(),mobileOpen=ref(false),accountOpen=ref(false),accountTrigger=ref<HTMLElement|null>(null)
const activeSection=computed(()=>route.name==='session-detail'?'sessions':route.name),activeSubject=computed(()=>String(route.query.subject||''))
const accountItems=computed(()=>[{id:'settings',label:t('settings'),run:()=>{location.assign('/settings')}},{id:'logout',label:t('signOut'),run:()=>emit('logout')}])
function toggle(){if(window.innerWidth<900)mobileOpen.value=!mobileOpen.value;else emit('update:collapsed',!props.collapsed)}
onMounted(()=>window.addEventListener('learning:open-navigation',toggle))
onUnmounted(()=>window.removeEventListener('learning:open-navigation',toggle))
const navigationItems=computed(()=>[
{id:'today',to:'/today',label:t('today'),icon:Clock,active:activeSection.value==='today'},
{id:'trends',to:'/trends',label:t('trends'),icon:DataAnalysis,active:activeSection.value==='trends'},
{id:'sessions',to:'/sessions',label:t('sessions'),icon:List,active:activeSection.value==='sessions'&&!activeSubject.value},
{id:'issues',to:'/issues',label:t('issues'),icon:Guide,active:activeSection.value==='issues'},
...(['math','english','major','training'] as const).map(subject=>({id:'subject-'+subject,to:{path:'/sessions',query:{subject}},label:t(subject==='math'?'mathematics':subject),active:activeSection.value==='sessions'&&activeSubject.value===subject}))
])
watch(()=>route.fullPath,()=>{mobileOpen.value=false;accountOpen.value=false})
</script>
<template><SharedSidebar :collapsed="collapsed" v-model:mobile-open="mobileOpen" label="Learning OS navigation" @update:collapsed="emit('update:collapsed',$event)"><template #workspace><RouterLink class="timer-workspace-title" to="/today">Learning OS</RouterLink></template><template #primary><nav class="timer-workspace-links" aria-label="Switch workspace"><a href="https://47.95.10.128/today" aria-current="page">Timer</a><a href="https://47.95.10.128/drill/practice">Drill</a><a href="https://47.95.10.128/ei/practice">EI</a></nav><GlobalSearch/><CustomizableNavigation workspace="timer" :items="navigationItems"/></template><template #footer><button ref="accountTrigger" type="button" class="timer-account" aria-haspopup="menu" :aria-expanded="accountOpen" @click="accountOpen=!accountOpen"><span>{{ username.slice(0,1).toUpperCase() }}</span><strong>{{ username }}<small v-if="preferences.pendingCount.value || ['error','offline','conflict'].includes(preferences.status.value)">预设待同步</small></strong><Setting aria-hidden="true"/></button><UiMenu v-model:open="accountOpen" :anchor="accountTrigger" :items="accountItems" :label="t('account')"/></template></SharedSidebar></template>
<style scoped>.timer-workspace-title{font-size:15px;font-weight:600;text-decoration:none;color:var(--text-primary)}.timer-workspace-links{display:flex;gap:4px;margin-bottom:8px}.timer-workspace-links a{flex:1;min-height:36px;padding:8px 4px;border-radius:6px;text-align:center;text-decoration:none;color:var(--text-secondary);font-size:13px}.timer-workspace-links a[aria-current],.timer-workspace-links a:hover{background:var(--surface-selected);color:var(--text-primary)}.timer-account{display:flex;align-items:center;gap:8px;width:100%;min-height:44px;padding:8px;border:0;border-radius:6px;background:transparent;color:var(--text-primary);cursor:pointer}.timer-account>span{display:grid;place-items:center;width:28px;height:28px;border-radius:6px;background:var(--surface-selected)}.timer-account strong{flex:1;min-width:0;text-align:left;overflow:hidden;text-overflow:ellipsis;font-size:14px;font-weight:500}.timer-account svg{width:16px;height:16px}@media(pointer:coarse){.timer-workspace-links a{min-height:44px}}.timer-account small{display:block;font-size:12px;color:var(--status-review)}.timer-workspace-title{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}</style>
