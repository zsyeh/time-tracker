<script setup lang="ts">
import { Moon, Sunny } from '@element-plus/icons-vue'
import { useUiPreferences, type UiLanguage, type UiScheme } from '../../lib/uiPreferences'

const { language, scheme, setLanguage, setScheme, t } = useUiPreferences()
</script>

<template>
  <div class="sidebar-preferences">
    <div class="scheme-switcher" :aria-label="t('appearance')">
      <button type="button" :class="{ active: scheme === 'dark' }" :aria-label="t('dark')" :title="t('dark')" @click="setScheme('dark' as UiScheme)"><el-icon><Moon /></el-icon></button>
      <button type="button" :class="{ active: scheme === 'light' }" :aria-label="t('light')" :title="t('light')" @click="setScheme('light' as UiScheme)"><el-icon><Sunny /></el-icon></button>
    </div>
    <label class="language-switcher">
      <span class="sr-only">{{ t('language') }}</span>
      <select :value="language" :aria-label="t('language')" @change="setLanguage(($event.target as HTMLSelectElement).value as UiLanguage)">
        <option value="en">EN</option>
        <option value="zh-CN">中文</option>
        <option value="ja">日本語</option>
      </select>
    </label>
  </div>
</template>
