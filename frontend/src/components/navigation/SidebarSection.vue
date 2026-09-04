<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { ArrowDown } from '@element-plus/icons-vue'

const props = withDefaults(defineProps<{
  title: string
  storageKey: string
  defaultExpanded?: boolean
}>(), { defaultExpanded: true })

const expanded = ref(props.defaultExpanded)

onMounted(() => {
  try {
    const saved = localStorage.getItem(props.storageKey)
    if (saved !== null) expanded.value = saved === 'true'
  } catch { /* Private browsing may disable storage. */ }
})

watch(expanded, (value) => {
  try { localStorage.setItem(props.storageKey, String(value)) } catch { /* Ignore storage failures. */ }
})
</script>

<template>
  <section class="sidebar-section" :class="{ expanded }">
    <button type="button" class="sidebar-section-toggle" :aria-expanded="expanded" @click="expanded = !expanded">
      <span>{{ title }}</span><el-icon><ArrowDown /></el-icon>
    </button>
    <div v-show="expanded" class="sidebar-section-items"><slot /></div>
  </section>
</template>
