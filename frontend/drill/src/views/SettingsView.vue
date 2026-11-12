<script setup lang="ts">
import ImageCopyScaleSetting from '../components/ImageCopyScaleSetting.vue'
import FontSizeSelector from '../../../shared/ui/FontSizeSelector.vue'
import SidebarCustomization from '../../../shared/ui/SidebarCustomization.vue'
import PreferenceSyncStatus from '../../../shared/ui/PreferenceSyncStatus.vue'
import { onMounted, ref } from 'vue'
import { api } from '../lib/api'
import { useUiPreferences, type UiLanguage } from '../lib/uiPreferences'
import { runtimeWorkspace } from '../lib/runtimePath'
import { uiText } from '../lib/uiText'
import { usePracticePreferences } from '../lib/practicePreferences'
import { useAppearance } from '../../../shared/appearance/preferences'
import AppearanceSelector from '../../../shared/ui/AppearanceSelector.vue'
import AccentColorPicker from '../../../shared/ui/AccentColorPicker.vue'
const { language, setLanguage, t } = useUiPreferences()
const { appearance, accent, setAppearance, setAccent } = useAppearance()
const { nextMode, pageTurnCopyMode, reviewAutoNext, masteredAutoNext, imageCopyScale } = usePracticePreferences()
const username = ref('')
const error = ref('')
const timerSettings = 'https://47.95.10.128/settings'
onMounted(async () => {
  try { username.value = (await api<{ user: { username: string } }>('/api/auth/session/')).user.username }
  catch (reason) { error.value = (reason as Error).message }
})
</script>
<template>
  <section class="page drill-settings">
    <header class="page-header"><div><h1>{{ uiText('设置') }}</h1><p>{{ uiText('管理外观、语言与账户。预设绑定账号并跨设备同步。') }}</p></div></header>
    <PreferenceSyncStatus/><p v-if="error" class="error-state" role="alert">{{ error }}</p>
    <section class="settings-group" aria-labelledby="settings-account"><h2 id="settings-account">{{ uiText('账户') }}</h2><div class="settings-rows"><div class="settings-row"><span>{{ uiText('当前用户') }}</span><span>{{ username || '…' }}</span></div><a class="settings-row" href="/accounts/2fa/"><span>{{ uiText('登录安全') }}</span><span>{{ uiText('管理 Passkey') }} <b aria-hidden="true">›</b></span></a></div></section>
    <section class="settings-group" aria-labelledby="settings-appearance"><h2 id="settings-appearance">{{ t('appearance') }}</h2><div class="settings-rows"><div class="settings-row"><span><strong>{{ t('appearance') }}</strong><small>{{ uiText('跟随系统，或固定使用浅色与深色。') }}</small></span><AppearanceSelector :model-value="appearance" @update:model-value="setAppearance" /></div><div class="settings-row accent-row"><span><strong>{{ uiText('强调色') }}</strong><small>{{ uiText('仅用于交互控件，页面背景保持中性。') }}</small></span><AccentColorPicker :model-value="accent" @update:model-value="setAccent" /></div></div></section>
    <section class="settings-group"><h2>文字大小</h2><div class="settings-rows"><FontSizeSelector/></div></section><section id="sidebar" class="settings-group"><SidebarCustomization :workspace="runtimeWorkspace"/></section>
    <section class="settings-group" aria-labelledby="settings-general"><h2 id="settings-general">{{ uiText('通用') }}</h2><div class="settings-rows"><label class="settings-row"><span>{{ t('language') }}</span><select :value="language" @change="setLanguage(($event.target as HTMLSelectElement).value as UiLanguage)"><option value="en">English</option><option value="zh-CN">中文</option><option value="ja">日本語</option></select></label></div></section>
    <section class="settings-group" aria-labelledby="settings-practice"><h2 id="settings-practice">{{ uiText('练习偏好') }}</h2><div class="settings-rows"><label class="settings-row"><span>{{ uiText('翻题顺序') }}</span><select v-model="nextMode"><option value="sequential">{{ uiText('顺序刷题') }}</option><option value="unattempted">{{ uiText('未做题') }}</option><option value="review">{{ uiText('待复习') }}</option><option value="overdue">{{ uiText('到期复习') }}</option></select></label><label class="settings-row"><span>{{ uiText('掌握后自动下一题') }}</span><input v-model="masteredAutoNext" type="checkbox" role="switch" /></label><label class="settings-row"><span>{{ uiText('待复习后自动下一题') }}</span><input v-model="reviewAutoNext" type="checkbox" role="switch" /></label><label class="settings-row"><span><strong>{{ uiText('翻题时复制') }}</strong><small>{{ uiText('使用浏览器允许的剪贴板能力。') }}</small></span><select v-model="pageTurnCopyMode"><option value="off">{{ uiText('关闭') }}</option><option value="link">{{ uiText('题目链接') }}</option><option value="image">{{ uiText('题图') }}</option></select></label><ImageCopyScaleSetting v-model="imageCopyScale"/></div></section>
    <section class="settings-group" aria-labelledby="settings-management"><h2 id="settings-management">{{ uiText('管理') }}</h2><div class="settings-rows"><a class="settings-row" :href="`${timerSettings}?section=security`"><span>{{ uiText('隐私与数据加密') }}</span><b aria-hidden="true">›</b></a><a class="settings-row" :href="`${timerSettings}?section=data`"><span>{{ uiText('数据导出') }}</span><b aria-hidden="true">›</b></a><a class="settings-row" :href="`${timerSettings}?section=organization`"><span>{{ uiText('任务预设与标签') }}</span><b aria-hidden="true">›</b></a><a class="settings-row" :href="`${timerSettings}?section=invitations`"><span>{{ uiText('邀请码') }}</span><b aria-hidden="true">›</b></a><a class="settings-row" :href="`${timerSettings}?section=shortcuts`"><span>{{ uiText('快捷指令与自动化') }}</span><b aria-hidden="true">›</b></a></div><p>{{ uiText('管理功能在 Learning OS 中打开，并沿用当前账户权限。') }}</p></section>
    <section class="settings-group" aria-labelledby="settings-source"><h2 id="settings-source">{{ uiText('题库来源') }}</h2><div class="settings-rows source-copy"><template v-if="runtimeWorkspace === 'drill'"><strong>{{ uiText('感谢 CXY') }}</strong><p>{{ uiText('题库源资料由 Bilibili 创作者 cxy（澄潇宇）收集整理；可确认时会另行标注 PDF 作者。') }}</p></template><template v-else><strong>892 · EI</strong><p>{{ uiText('已从用户提供的 Markdown 题库导入基础例题与简答题，公式按原始 LaTeX 渲染。') }}</p></template></div></section>
  </section>
</template>
<style scoped>
.drill-settings { max-width:880px; min-width:0; } .page-header h1 { margin:0; } .page-header p { font-size:14px; margin-top:8px; color:var(--text-secondary); }
.settings-group { margin:24px 0; } h2 { font-size:16px; margin:0 0 12px; font-weight:600; } .settings-rows { background:var(--surface-subtle); border-radius:8px; padding:0 16px; }
.settings-row { min-height:56px; display:flex; align-items:center; justify-content:space-between; gap:24px; padding:12px 0; font-size:14px; color:var(--text-primary); text-decoration:none; }
.settings-row + .settings-row { border-top:1px solid var(--border-subtle); } .settings-row > span { min-width:0; } .settings-row > span:last-child { color:var(--text-secondary); } strong { font-weight:500; } small { display:block; color:var(--text-secondary); font-size:12px; line-height:1.5; margin-top:4px; }
input[type=checkbox] { width:20px; height:20px; accent-color:var(--accent-solid); } .settings-row b { color:var(--text-secondary); font-size:18px; font-weight:400; } a.settings-row:hover { color:var(--accent-ink); } select { min-height:44px; max-width:50%; border:0; background:transparent; color:var(--text-primary); font:inherit; padding:8px; }
.accent-row { align-items:start; } .accent-row > :last-child { max-width:320px; } .source-copy { padding:16px; font-size:14px; } .source-copy p, .settings-group > p { font-size:13px; line-height:1.6; color:var(--text-secondary); margin:8px 0 0; }
@media(min-width:1200px) { .drill-settings { padding-right:32px; } }
@media(max-width:600px) { .settings-row { gap:12px; flex-wrap:wrap; } .accent-row > :last-child { max-width:100%; } }
</style>
