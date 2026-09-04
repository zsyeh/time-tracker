<script setup lang="ts">
import type { Component } from 'vue'
import type { RouteLocationRaw } from 'vue-router'

withDefaults(defineProps<{
  label: string
  to?: RouteLocationRaw
  icon?: Component
  active?: boolean
  disabled?: boolean
}>(), {
  to: undefined,
  icon: undefined,
  active: false,
  disabled: false,
})
</script>

<template>
  <RouterLink v-if="to && !disabled" :to="to" class="sidebar-item" :class="{ active }">
    <el-icon v-if="icon"><component :is="icon" /></el-icon>
    <span v-else class="sidebar-item-marker" />
    <span>{{ label }}</span>
  </RouterLink>
  <button v-else type="button" class="sidebar-item" :class="{ active }" :disabled="disabled">
    <el-icon v-if="icon"><component :is="icon" /></el-icon>
    <span v-else class="sidebar-item-marker" />
    <span>{{ label }}</span>
  </button>
</template>
