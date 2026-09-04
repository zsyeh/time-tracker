<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { ArrowDown } from '@element-plus/icons-vue'

withDefaults(defineProps<{
  label: string
  align?: 'start' | 'end'
  width?: string
}>(), { align: 'start', width: '248px' })

const open = ref(false)
const root = ref<HTMLElement | null>(null)

function close() { open.value = false }
function toggle() { open.value = !open.value }
function onPointerDown(event: PointerEvent) {
  if (open.value && root.value && !root.value.contains(event.target as Node)) close()
}
function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') close()
}

onMounted(() => {
  document.addEventListener('pointerdown', onPointerDown)
  document.addEventListener('keydown', onKeydown)
})
onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onPointerDown)
  document.removeEventListener('keydown', onKeydown)
})

defineExpose({ close })
</script>

<template>
  <div ref="root" class="menu-popover" :class="`align-${align}`">
    <button type="button" class="menu-popover-trigger" :aria-expanded="open" aria-haspopup="menu" @click="toggle">
      <slot name="trigger"><span>{{ label }}</span><el-icon><ArrowDown /></el-icon></slot>
    </button>
    <button v-if="open" type="button" class="menu-popover-backdrop" tabindex="-1" aria-label="Close menu" @click="close" />
    <div v-if="open" class="menu-popover-surface" :style="{ '--menu-width': width }" role="menu" :aria-label="label">
      <header><span>{{ label }}</span><button type="button" aria-label="Close menu" @click="close">×</button></header>
      <div class="menu-popover-content"><slot :close="close" /></div>
    </div>
  </div>
</template>
