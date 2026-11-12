<script setup lang="ts">
import { computed } from 'vue'
import { ref } from 'vue'
import { readLegacyPreferences, clearLegacyPreferences } from '../preferences/legacy'
import type { PreferenceKey } from '../preferences/schema'
import { useAccountPreferences } from '../preferences/store'
const store=useAccountPreferences()
const legacy=ref(readLegacyPreferences())
const names:Record<string,string>={appearance:'外观',accent:'强调色',font:'字体大小',language:'语言','progress.drill':'Drill学习目标','progress.ei':'EI学习目标'}
function importLegacy(){for(const [key,value] of Object.entries(legacy.value))store.set(key as PreferenceKey,value as never);clearLegacyPreferences();legacy.value={}}
function dismissLegacy(){clearLegacyPreferences();legacy.value={}}

const text=computed(()=>store.status.value==='saving'?'正在同步账号预设…':store.status.value==='saved'?'已同步到账号':store.message.value || (store.pendingCount.value?'更改已保存在本机，等待同步。':''))
</script>
<template><div class="preference-sync-status" :class="{warning:['offline','error','conflict'].includes(store.status.value)}" aria-live="polite"><span>{{ text }}</span><template v-if="store.conflicts.value.length"><span>冲突：{{ store.conflicts.value.map(key=>names[key] || (key.startsWith('sidebar.')?'侧栏布局':key.startsWith('filters.')?'筛选预设':'做题偏好')).join('、') }}</span><button type="button" class="ui-button ui-button--secondary" @click="store.useServer()">使用服务器版本</button><button type="button" class="ui-button ui-button--secondary" @click="store.keepMine()">保留本机更改</button></template><button v-else-if="['offline','error'].includes(store.status.value) || store.pendingCount.value" type="button" class="ui-button ui-button--secondary" @click="store.refresh().then(()=>store.flush())">重试同步</button><template v-if="store.userId.value && Object.keys(legacy).length"><span>检测到此设备旧版学习预设（未绑定账号）。</span><button type="button" class="ui-button ui-button--secondary" @click="importLegacy">导入到当前账号</button><button type="button" class="ui-button ui-button--secondary" @click="dismissLegacy">忽略旧偏好</button></template></div></template>
<style scoped>.preference-sync-status{display:flex;flex-wrap:wrap;align-items:center;gap:8px;min-height:36px;color:var(--text-secondary);font-size:12px;margin:8px 0 16px}.warning{color:var(--status-review)}.preference-sync-status button{min-height:44px;font-size:13px}</style>
