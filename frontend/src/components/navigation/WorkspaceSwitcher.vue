<script setup lang="ts">
import { computed, ref } from 'vue'
import { ArrowDown } from '@element-plus/icons-vue'

const open = ref(false)
const workspaceLinks = computed(() => {
  return [
    { label: 'Learning OS', href: 'https://47.95.10.128/today', current: true },
    { label: 'Mathematics Drill', href: 'https://47.95.10.128/drill/practice', current: false },
    { label: '892 Practice', href: 'https://47.95.10.128/ei/practice', current: false },
  ]
})
</script>

<template>
  <div class="workspace-switcher">
    <button type="button" class="workspace-trigger" :aria-expanded="open" @click="open = !open">
      <span class="workspace-mark">L</span>
      <span class="workspace-youtube-mark" aria-hidden="true"><svg viewBox="0 0 36 25" focusable="false"><rect x="1" y="2" width="34" height="21" rx="6" /><path d="M15 8.1 24 12.5 15 16.9Z" /></svg></span>
      <strong class="workspace-name-default">Learning OS</strong><strong class="workspace-name-youtube">Premium</strong><el-icon><ArrowDown /></el-icon>
    </button>
    <div v-if="open" class="workspace-menu">
      <a v-for="item in workspaceLinks" :key="item.label" :href="item.href" :class="{ current: item.current }" @click="open = false"><span>{{ item.label }}</span><small v-if="item.current">Current</small></a>
    </div>
  </div>
</template>
