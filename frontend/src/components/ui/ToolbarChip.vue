<script setup lang="ts">
withDefaults(defineProps<{
  label: string
  active?: boolean
  count?: number
  pressed?: boolean
}>(), { active: false, count: undefined, pressed: undefined })

defineEmits<{ click: [] }>()
</script>

<template>
  <button type="button" class="toolbar-chip" :class="{ active }" :aria-pressed="pressed" @click="$emit('click')">
    <slot name="icon" /><span>{{ label }}</span><b v-if="count !== undefined">{{ count }}</b><slot name="suffix" />
  </button>
</template>
